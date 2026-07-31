# Numa

[![CI](https://github.com/open-numa-ai/numa/actions/workflows/ci.yml/badge.svg)](https://github.com/open-numa-ai/numa/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

Numa is a modular Python framework for building intelligent agent systems. It provides small, explicit abstractions for agents, task execution, tools, memory, context, configuration, and future multi-agent coordination.

> **Project status:** v0.2 integration boundaries are feature-complete. The public APIs may evolve before the first stable release.

## Why Numa?

Agent applications often couple model providers, orchestration, state, and tools into one implementation. Numa keeps these responsibilities separate so applications can replace infrastructure without rewriting agent behavior.

The initial release intentionally includes no LLM integration or complex planning algorithm.

## Features

- Typed `Agent`, `Tool`, and `Memory` extension points
- Pydantic-backed tool input/output schemas and runtime validation
- Entry-point discovery for third-party Agent and Tool plugins
- SQLite-backed persistent memory for JSON-compatible values
- Provider-neutral model request and response interfaces
- Structured Agent, Tool, and Provider lifecycle events
- Synchronous `AgentRuntime` with explicit task lifecycle handling
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

Collect structured lifecycle events:

```python
from numa import AgentRuntime, EventBus, InMemoryEventHandler, Task
from numa.agents import EchoAgent

collector = InMemoryEventHandler()
runtime = AgentRuntime(event_bus=EventBus([collector]))
runtime.run(EchoAgent(), Task(description="Hello"))

print([event.type.value for event in collector.events])
```

See the [Quick Start guide](docs/quick-start.md) for configuration and development commands.

## Architecture

```text
Application
    |
AgentRuntime ---- Tool registry
    |                 |
  Agent             Tools
    |
Task + Context ---- Memory
```

Numa depends on abstractions at its boundaries. Agents own task behavior, the runtime owns execution lifecycle, tools expose capabilities, and memory adapters own persistence.

See [Architecture](docs/architecture.md) for module responsibilities and extension points.
See [Plugins](docs/plugins.md) to publish Agent and Tool extensions as separate packages.
See [Model Providers](docs/model-providers.md) to implement optional vendor adapters.
See [Structured Events](docs/events.md) to integrate observability handlers.

## Development

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

Read [Contributing](CONTRIBUTING.md) before opening an issue or pull request.

## Roadmap

See [ROADMAP.md](ROADMAP.md) for planned runtime, plugin, asynchronous, persistence, and multi-agent capabilities.

## License

Numa is licensed under the [Apache License 2.0](LICENSE).
