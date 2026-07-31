"""Deterministic tools used in examples and integration tests."""

from typing import Any

from pydantic import BaseModel, Field

from numa.tools.base import Tool, ToolInput


class AddInput(ToolInput):
    """Validated input for AddTool."""

    left: int = Field(description="Left operand")
    right: int = Field(description="Right operand")


class AddOutput(BaseModel):
    """Validated output for AddTool."""

    result: int


class AddTool(Tool):
    """Add two integers without external dependencies."""

    @property
    def name(self) -> str:
        return "add"

    @property
    def description(self) -> str:
        return "Add two integers."

    @property
    def input_model(self) -> type[BaseModel]:
        return AddInput

    @property
    def output_model(self) -> type[BaseModel]:
        return AddOutput

    def execute(self, **arguments: Any) -> dict[str, int]:
        return {"result": int(arguments["left"]) + int(arguments["right"])}
