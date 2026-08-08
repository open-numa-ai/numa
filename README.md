# Numa

[![CI](https://github.com/open-numa-ai/numa/actions/workflows/ci.yml/badge.svg)](https://github.com/open-numa-ai/numa/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

Numa is a small, provider-neutral Python runtime foundation for embedding agent components in applications. It provides explicit contracts for agents, tasks, tools, memory, context, and execution lifecycle without choosing an LLM vendor or agent strategy for the application.

> **Project status:** Numa is pre-alpha. Roadmap versions group capabilities; they are not published package versions or production-readiness guarantees. Public APIs may evolve before the first stable release.

## Why Numa?

Agent applications often couple model providers, execution lifecycle, state, and tools into one implementation. Numa keeps these responsibilities separate so applications can replace infrastructure without rewriting agent behavior.

Numa is designed to be embedded beneath application-level agent logic. Applications and optional packages own prompts, planning, model SDK integration, autonomous loops, and deployment. Numa owns narrow component contracts and predictable local execution around them.

## Features

- Typed `Agent`, `Tool`, and `Memory` extension points
- Pydantic-backed tool input/output schemas and runtime validation
- Entry-point discovery for third-party Agent and Tool plugins
- SQLite-backed persistent memory for JSON-compatible values
- Provider-neutral model request and response interfaces
- Provider-backed synchronous `LLMAgent` reference implementation
- Structured Agent, Tool, and Provider lifecycle events
- Synchronous `AgentRuntime` with explicit task lifecycle handling
- Parallel `AsyncAgent`, `AsyncTool`, and `AsyncAgentRuntime` contracts
- Explicit async timeout, cancellation, and bounded retry policies
- Versioned Task snapshots with SQLite persistence and explicit resume
- Ordered synchronous and asynchronous Runtime middleware composition
- Explicit Tool allowlist, denylist, and custom permission policies
- Sequential, conditional, and explicit asynchronous parallel workflow composition
- Framework-neutral `Task`, `Message`, and `Context` models
- YAML, JSON, environment, and default configuration layers
- Standard-library logging with a unified Numa namespace
- Basic `numa init` and `numa run example_agent` commands
- Python 3.11+ support with uv, Ruff, Mypy, and Pytest

## Quick Start

Install [uv](https://docs.astral.sh/uv/), clone the repository, and synchronize the environment:

```bash
git clone https://github.com/open-numa-ai/numa.git
cd numa
uv sync --all-groups
```

Create a default configuration and run the built-in example agent:

```bash
uv run numa init
uv run numa run example_agent --task "Hello, Numa"
```

Or use the public Python API:

```python
from numa import AgentRuntime, Task
from numa.agents import EchoAgent

result = AgentRuntime().run(EchoAgent(), Task(description="Hello, Numa"))
print(result.content)
```

Register and execute a schema-backed tool:

```python
from numa import AgentRuntime
from numa.tools import AddTool

runtime = AgentRuntime()
runtime.register_tool(AddTool())

print(runtime.execute_tool("add", left=2, right=3))
```

Inspect installed plugins:

```bash
uv run numa plugins list
uv run numa plugins list --type agent
```

Persist runtime memory locally:

```python
from numa import AgentRuntime
from numa.memory import SQLiteMemory

with SQLiteMemory("numa-memory.db") as memory:
    runtime = AgentRuntime(memory=memory)
    memory.set("project", {"name": "Numa"})
    print(runtime.memory.get("project"))
```

Build Agents against a provider-neutral model boundary:

```python
from numa import Message, MessageRole, ModelRequest
from numa.providers import EchoModelProvider

provider = EchoModelProvider()
response = provider.generate(
    ModelRequest(messages=(Message(role=MessageRole.USER, content="Hello"),))
)
print(response.message.content)
```

Compose the same provider boundary with the reference Agent and Runtime:

```python
from numa import AgentRuntime, Task
from numa.agents import LLMAgent
from numa.providers import EchoModelProvider

agent = LLMAgent(EchoModelProvider(), system_prompt="Be concise.")
result = AgentRuntime().run(agent, Task(description="Hello"))
print(result.content)
```

Collect structured lifecycle events:

```python
from numa import AgentRuntime, EventBus, InMemoryEventHandler, Task
from numa.agents import EchoAgent

collector = InMemoryEventHandler()
runtime = AgentRuntime(event_bus=EventBus([collector]))
runtime.run(EchoAgent(), Task(description="Hello"))

print([event.type.value for event in collector.events])
```

Run independent Agent tasks concurrently:

```python
import asyncio

from numa import AsyncAgentRuntime, Task
from numa.agents import AsyncEchoAgent


async def main() -> None:
    results = await AsyncAgentRuntime().gather(
        (AsyncEchoAgent(), Task(description="first")),
        (AsyncEchoAgent(), Task(description="second")),
    )
    print([result.content for result in results])


asyncio.run(main())
```

Compose Agent steps above the Runtime while preserving each child Task lifecycle:

```python
from numa import AgentRuntime, AgentStep, SequentialWorkflow, Task
from numa.agents import EchoAgent

workflow = SequentialWorkflow(
    [
        AgentStep(EchoAgent(), name="draft"),
        AgentStep(
            EchoAgent(),
            name="review",
            task_factory=lambda state: Task(
                description=f"Review: {state.result('draft').message.content}"
            ),
        ),
    ]
)
result = workflow.run(AgentRuntime(), Task(description="Write an update"))
print(result.final_message.content if result.final_message else "no result")
```

See the [Quick Start guide](docs/quick-start.md) for configuration and development commands.

## Architecture

```text
Application
    |
Runtime ---- Tool registry
    |             |
Agent         Tools
    |
Task + Context ---- Memory
    |
Task Store (optional)
```

Numa depends on abstractions at its boundaries. Applications compose the system, Agents own task behavior, the Runtime owns execution lifecycle, Tools expose capabilities, and adapters own model and storage integration.

See [Architecture](docs/architecture.md) for module responsibilities and extension points.
See [Plugins](docs/plugins.md) to publish Agent and Tool extensions as separate packages.
See [Model Providers](docs/model-providers.md) to implement optional vendor adapters.
See [Structured Events](docs/events.md) to integrate observability handlers.
See [Runtime Resilience Policies](docs/runtime-policies.md) to configure async deadlines and retries.
See [Task Persistence and Resume](docs/task-persistence.md) for durable lifecycle recovery.
See [Runtime Middleware](docs/runtime-middleware.md) to wrap Agent and Tool component calls.
See [Tool Permission Policies](docs/tool-permissions.md) to authorize Runtime-managed Tool calls.
See [Workflow Composition](docs/workflows.md) to compose sequential, conditional, and asynchronous parallel Agent steps.

## Development

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

Read [Contributing](CONTRIBUTING.md) before opening an issue or pull request.

## Roadmap

See [ROADMAP.md](ROADMAP.md) for completed capability groups and possible future directions.

## License

Numa is licensed under the [Apache License 2.0](LICENSE).
