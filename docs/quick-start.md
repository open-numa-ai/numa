# Quick Start

This guide runs Numa's current framework foundation without an LLM provider.

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)
- Git

## Install from Source

```bash
git clone https://github.com/open-numa-ai/numa.git
cd numa
uv sync --all-groups
```

`uv sync` creates an isolated environment and installs Numa with its development tools.

## Initialize Configuration

```bash
uv run numa init
```

This creates `numa.yaml` in the current directory. It will not overwrite an existing file.

```yaml
logging:
  level: INFO
  format: "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
runtime:
  max_steps: 10
```

Configuration precedence is:

1. Built-in defaults
2. YAML or JSON configuration file
3. Environment variables

Supported environment variables:

- `NUMA_LOG_LEVEL`
- `NUMA_LOG_FORMAT`
- `NUMA_RUNTIME_MAX_STEPS`

## Run the Example Agent

```bash
uv run numa run example_agent --task "Hello, Numa"
```

The example agent echoes the task through `AgentRuntime`. It validates the framework lifecycle without performing model inference.

## Use the Python API

```python
from numa import AgentRuntime, Context, Message, MessageRole, Task
from numa.agents import Agent


class GreetingAgent(Agent):
    @property
    def name(self) -> str:
        return "greeting"

    def run(self, task: Task, context: Context) -> Message:
        return Message(
            role=MessageRole.ASSISTANT,
            content=f"Received: {task.description}",
        )


result = AgentRuntime().run(GreetingAgent(), Task(description="Say hello"))
print(result.content)
```

## Define and Run a Tool

Tool input models inherit from `ToolInput`, which rejects undeclared arguments and exposes a standard JSON Schema. Output validation is optional.

```python
from typing import Any

from pydantic import BaseModel

from numa import AgentRuntime
from numa.tools import Tool, ToolInput


class MultiplyInput(ToolInput):
  left: int
  right: int


class MultiplyOutput(BaseModel):
  result: int


class MultiplyTool(Tool):
  @property
  def name(self) -> str:
    return "multiply"

  @property
  def input_model(self) -> type[BaseModel]:
    return MultiplyInput

  @property
  def output_model(self) -> type[BaseModel]:
    return MultiplyOutput

  def execute(self, **arguments: Any) -> dict[str, int]:
    return {"result": arguments["left"] * arguments["right"]}


runtime = AgentRuntime()
runtime.register_tool(MultiplyTool())
result = runtime.execute_tool("multiply", left=6, right=7)
print(result)
```

Use `tool.input_schema` and `tool.output_schema` when another system needs JSON Schema. Calls through `AgentRuntime.execute_tool()` validate both boundaries. Direct `Tool.execute()` calls intentionally bypass framework validation.

## Inspect Installed Plugins

Numa discovers built-in and third-party components through Python Entry Points.

```bash
uv run numa plugins list
uv run numa plugins list --type agent
uv run numa plugins list --type tool
```

Run any discovered Agent by its registered name:

```bash
uv run numa run example_agent --task "Hello from a plugin"
```

Plugin packages use the `numa.agents` and `numa.tools` Entry Point groups. See the [Plugin guide](plugins.md) for package declarations and factory examples.

## Quality Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest --cov=numa
```

The same checks run in GitHub Actions for Python 3.11, 3.12, and 3.13.