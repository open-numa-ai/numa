from typing import Any

import pytest
from pydantic import BaseModel

from numa.core import ToolExecutionError, ToolNotFoundError, ToolValidationError
from numa.runtime import AgentRuntime
from numa.tools import AddTool, Tool


class NoArgumentsTool(Tool):
    @property
    def name(self) -> str:
        return "no_arguments"

    def execute(self, **arguments: Any) -> str:
        assert arguments == {}
        return "done"


class InvalidOutput(BaseModel):
    count: int


class InvalidOutputTool(NoArgumentsTool):
    @property
    def name(self) -> str:
        return "invalid_output"

    @property
    def output_model(self) -> type[BaseModel]:
        return InvalidOutput

    def execute(self, **arguments: Any) -> dict[str, str]:
        del arguments
        return {"count": "not-an-integer"}


class FailingTool(NoArgumentsTool):
    @property
    def name(self) -> str:
        return "failing"

    def execute(self, **arguments: Any) -> str:
        del arguments
        raise RuntimeError("tool failed")


def test_tool_exposes_json_schemas() -> None:
    tool = AddTool()

    assert tool.input_schema["required"] == ["left", "right"]
    assert tool.input_schema["properties"]["left"]["type"] == "integer"
    assert tool.output_schema is not None
    assert tool.output_schema["properties"]["result"]["type"] == "integer"


def test_runtime_validates_normalizes_and_executes_tool() -> None:
    runtime = AgentRuntime()
    runtime.register_tool(AddTool())

    result = runtime.execute_tool("add", left="2", right=3)

    assert result == {"result": 5}


def test_tool_without_arguments_uses_empty_input_schema() -> None:
    runtime = AgentRuntime()
    tool = NoArgumentsTool()
    runtime.register_tool(tool)

    assert tool.input_schema["additionalProperties"] is False
    assert runtime.execute_tool("no_arguments") == "done"


def test_runtime_rejects_unknown_tool() -> None:
    with pytest.raises(ToolNotFoundError, match="missing"):
        AgentRuntime().execute_tool("missing")


def test_runtime_rejects_invalid_input() -> None:
    runtime = AgentRuntime()
    runtime.register_tool(AddTool())

    with pytest.raises(ToolValidationError, match="Invalid input"):
        runtime.execute_tool("add", left="invalid", right=3)

    with pytest.raises(ToolValidationError, match="Invalid input"):
        runtime.execute_tool("add", left=2, right=3, unexpected=True)


def test_runtime_rejects_invalid_output() -> None:
    runtime = AgentRuntime()
    runtime.register_tool(InvalidOutputTool())

    with pytest.raises(ToolValidationError, match="Invalid output"):
        runtime.execute_tool("invalid_output")


def test_runtime_wraps_tool_execution_errors() -> None:
    runtime = AgentRuntime()
    runtime.register_tool(FailingTool())

    with pytest.raises(ToolExecutionError, match="failing") as error:
        runtime.execute_tool("failing")

    assert isinstance(error.value.__cause__, RuntimeError)
