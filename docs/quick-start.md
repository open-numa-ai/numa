# Quick Start

This guide runs Numa's provider-neutral runtime foundation without a vendor LLM SDK.

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

The example agent echoes the task through `AgentRuntime`. It validates the Runtime lifecycle without performing model inference.

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

Use `tool.input_schema` and `tool.output_schema` when another system needs JSON Schema. Calls through `AgentRuntime.execute_tool()` validate both boundaries. Direct `Tool.execute()` calls intentionally bypass Runtime validation.

## Run Asynchronous Components

`AsyncAgentRuntime` mirrors the synchronous task, Tool validation, error, and event semantics while awaiting only explicit `AsyncAgent` and `AsyncTool` implementations.

```python
import asyncio

from numa import AsyncAgentRuntime, Task
from numa.agents import AsyncEchoAgent
from numa.tools import AsyncAddTool


async def main() -> None:
    runtime = AsyncAgentRuntime()
    runtime.register_tool(AsyncAddTool())
    messages = await runtime.gather(
        (AsyncEchoAgent(), Task(description="first")),
        (AsyncEchoAgent(), Task(description="second")),
    )
    total = await runtime.execute_tool("async_add", left=6, right=7)
    print([message.content for message in messages], total)


asyncio.run(main())
```

The async runtime does not implicitly run synchronous components in threads. Configure bounded retries and a total deadline with `ResiliencePolicy`:

```python
from numa import AsyncAgentRuntime, ResiliencePolicy, RetryPolicy

runtime = AsyncAgentRuntime(
    resilience_policy=ResiliencePolicy(
        timeout_seconds=30,
        retry=RetryPolicy(
            max_attempts=3,
            delay_seconds=0.25,
            retry_exceptions=(ConnectionError,),
        ),
    )
)
```

External cancellation remains cooperative and propagates `asyncio.CancelledError`. See [Runtime Resilience Policies](runtime-policies.md) for deadline, retry, Tool override, and event semantics.

## Persist and Resume Tasks

Configure a `TaskStore` to save Agent lifecycle snapshots and recover unfinished Tasks after recreating the Runtime:

```python
from numa import AgentRuntime, Task
from numa.agents import EchoAgent
from numa.tasks import SQLiteTaskStore

with SQLiteTaskStore("numa-tasks.db") as store:
    runtime = AgentRuntime(task_store=store)
    task = Task(description="durable work")
    runtime.run(EchoAgent(), task)

with SQLiteTaskStore("numa-tasks.db") as store:
    result = AgentRuntime(task_store=store).resume(EchoAgent(), task.id)
```

Completed Tasks return their stored result without another Agent call. Unfinished, failed, or cancelled Tasks replay the Agent invocation from the beginning with the same ID and Context. See [Task Persistence and Resume](task-persistence.md) for storage, identity, and idempotency semantics.

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

## Persist Memory with SQLite

`SQLiteMemory` stores JSON-compatible values in a local database using Python's standard SQLite driver.

```python
from numa import AgentRuntime
from numa.memory import SQLiteMemory

with SQLiteMemory("numa-memory.db") as memory:
    runtime = AgentRuntime(memory=memory)
    memory.set("preferences", {"language": "en", "topics": ["agents"]})
    print(runtime.memory.get("preferences"))
```

The adapter creates its table automatically. Use it as a context manager or call `close()` explicitly. Values must be valid JSON; arbitrary Python objects and non-finite numbers are rejected with `MemoryError`.

## Use a Model Provider

The provider contract separates Agent behavior from vendor SDKs. The built-in Echo Provider is deterministic and performs no model inference.

```python
from numa import Message, MessageRole, ModelRequest
from numa.providers import EchoModelProvider

provider = EchoModelProvider()
response = provider.generate(
    ModelRequest(
        messages=(Message(role=MessageRole.USER, content="Hello, Numa"),),
        parameters={"temperature": 0},
    )
)
print(response.message.content)
```

Concrete adapters implement `ModelProvider.generate()` and translate `ModelRequest` and `ModelResponse` at the SDK boundary. See [Model Providers](model-providers.md) for the contract and error semantics.

## Observe Structured Events

Attach one or more handlers to an `EventBus` to observe Agent and Tool execution:

```python
from numa import AgentRuntime, EventBus, InMemoryEventHandler, Task
from numa.agents import EchoAgent

collector = InMemoryEventHandler()
runtime = AgentRuntime(event_bus=EventBus([collector]))
runtime.run(EchoAgent(), Task(description="Hello"))

for event in collector.events:
    print(event.type.value, event.execution_id)
```

Use `InstrumentedModelProvider` to observe a Provider without changing its implementation. Handler failures are logged and do not interrupt Numa execution. See [Structured Events](events.md) for event fields, correlation, privacy, and custom handlers.

## Quality Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest --cov=numa
```

The same checks run in GitHub Actions for Python 3.11, 3.12, and 3.13.
