# Quick Start

This guide runs Numa's v0.1.0 foundation without an LLM provider.

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

## Quality Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest --cov=numa
```

The same checks run in GitHub Actions for Python 3.11, 3.12, and 3.13.