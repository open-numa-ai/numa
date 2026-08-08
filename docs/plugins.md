# Plugins

Numa uses Python Entry Points so external packages can provide Agents and Tools without modifying the core repository.

## Plugin Groups

- `numa.agents` registers Agent factories.
- `numa.tools` registers Tool factories.

Each Entry Point name is the public component name used by Numa. Its target must be a zero-argument callable that returns the corresponding component.

## Package Declaration

Declare plugins in the extension package's `pyproject.toml`:

```toml
[project.entry-points."numa.agents"]
research_agent = "numa_research:create_agent"

[project.entry-points."numa.tools"]
web_search = "numa_research:create_search_tool"
```

The factories can construct dependencies privately while exposing only Numa's public contracts:

```python
from numa.agents import Agent
from numa.tools import Tool

from numa_research.agents import ResearchAgent
from numa_research.tools import WebSearchTool


def create_agent() -> Agent:
    return ResearchAgent()


def create_search_tool() -> Tool:
    return WebSearchTool()
```

`ResearchAgent.name` must be `"research_agent"`, and `WebSearchTool.name` must be `"web_search"`. Numa rejects mismatches so CLI names and runtime identities remain consistent.

## Install and Inspect

Install the extension package into the same environment as Numa, then list discovered plugins:

```bash
uv pip install numa-research
uv run numa plugins list
uv run numa plugins list --type agent
uv run numa plugins list --type tool
```

Run a discovered Agent by name:

```bash
uv run numa run research_agent --task "Summarize this topic"
```

## Loading Semantics

Discovery is lazy. Listing records Entry Point names without importing plugin modules or invoking factories. Loading one broken plugin does not prevent another discovered plugin from loading.

Numa reports explicit errors for:

- Duplicate names, including conflicts with built-in plugins
- Entry Points that do not expose a callable factory
- Factory import or execution failures
- Factories that return the wrong component type
- Components whose `name` differs from the Entry Point name

## Security

Python plugins execute in the host process with the application's permissions. Install only trusted plugin packages. Runtime Tool permission policies can authorize calls to a loaded Tool, but they do not sandbox plugin imports, factories, or implementation code.
