# Architecture

Numa v0.1.0 establishes small interfaces and a synchronous execution path. It deliberately avoids model providers, planners, distributed queues, and multi-agent protocols until their requirements are proven by real integrations.

## Design Decisions

1. **Use a `src` layout.** Imports resolve from the installed package instead of accidentally resolving from the repository root.
2. **Separate data from behavior.** `Task`, `Message`, and `Context` are framework-neutral models. `Agent`, `Tool`, and `Memory` define behavioral boundaries.
3. **Keep orchestration thin.** `AgentRuntime` controls task lifecycle and dependency access, but does not implement agent strategy.
4. **Depend on abstractions.** Runtime and application code can replace memory and tool adapters without changing agents.
5. **Start synchronously.** A clear synchronous contract is easier to test. Async execution can be introduced as a parallel runtime contract when needed.
6. **Use standard library infrastructure where practical.** Logging and CLI behavior build on `logging` and `argparse`; PyYAML is the only runtime dependency.

## Repository Tree

```text
numa/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.yml
│   │   └── feature_request.yml
│   ├── workflows/
│   │   └── ci.yml
│   └── PULL_REQUEST_TEMPLATE.md
├── docs/
│   ├── architecture.md
│   ├── design.md
│   ├── quick-start.md
│   └── vision.md
├── examples/
│   └── basic_agent.py
├── src/
│   └── numa/
│       ├── agents/
│       │   ├── base.py
│       │   └── echo.py
│       ├── config/
│       │   └── settings.py
│       ├── core/
│       │   ├── exceptions.py
│       │   └── models.py
│       ├── memory/
│       │   ├── base.py
│       │   └── in_memory.py
│       ├── runtime/
│       │   └── runtime.py
│       ├── tools/
│       │   └── base.py
│       ├── utils/
│       │   └── logging.py
│       ├── cli.py
│       └── py.typed
├── tests/
│   └── unit/
├── CONTRIBUTING.md
├── LICENSE
├── pyproject.toml
├── README.md
└── ROADMAP.md
```

## Module Responsibilities

### `core`

Contains stable data contracts and the exception hierarchy. It has no provider, storage, or application policy.

- `Task` tracks a unit of work and its lifecycle.
- `Message` carries typed conversation output and metadata.
- `Context` owns ordered messages and execution-scoped metadata.
- `NumaError` gives callers one framework-level exception boundary.

### `agents`

Defines the `Agent` abstraction. An agent owns task-specific behavior and returns one `Message`. `EchoAgent` is a deterministic example, not an AI implementation.

### `runtime`

Coordinates an agent invocation. It changes task state, records results, appends output to context, exposes memory and registered tools, logs lifecycle events, and converts implementation failures into `AgentExecutionError`.

### `tools`

Defines named executable capabilities. Tool schemas, validation, permissions, and provider adapters remain extension concerns for later releases.

### `memory`

Defines minimal key-value memory operations. `InMemoryMemory` supports examples and tests; persistent adapters can implement the same contract.

### `config`

Loads typed defaults, JSON or YAML files, then environment overrides. Configuration remains immutable after loading so execution behavior is predictable.

### `utils`

Contains narrow shared infrastructure. The logging helper configures only the `numa` namespace, preserving control for embedding applications.

### `cli`

Provides project initialization and a basic agent runner. It is an adapter over public APIs rather than a separate execution engine.

## Execution Flow

```mermaid
sequenceDiagram
  participant App as Application or CLI
  participant Runtime as AgentRuntime
  participant Agent
  participant Context

  App->>Runtime: run(agent, task, context)
  Runtime->>Runtime: task.status = RUNNING
  Runtime->>Agent: run(task, context)
  Agent-->>Runtime: Message
  Runtime->>Context: add_message(message)
  Runtime->>Runtime: task.status = COMPLETED
  Runtime-->>App: Message
```

If an agent raises, the runtime marks the task failed, records the original error text, logs the exception, and raises `AgentExecutionError` with the original exception as its cause.

## Extension Points

- **Model integration:** implement an `Agent` that depends on a provider-specific client owned by the application.
- **Persistent memory:** implement `Memory` using SQLite, PostgreSQL, Redis, or a vector store.
- **Tool ecosystem:** implement `Tool` adapters and add schema validation and permission policy around registration.
- **Async runtime:** add an async agent contract and runtime without changing the synchronous API.
- **Planning:** compose tasks above `AgentRuntime`; do not embed planning policy into the base runtime.
- **Multi-agent collaboration:** add routing and message transport as a higher orchestration layer.
- **Observability:** attach structured, file, or telemetry handlers through the standard logging interface.
- **Plugins:** replace the CLI's built-in agent registry with Python entry-point discovery.

## Current Boundaries

The foundation does not include LLM calls, prompt templates, autonomous loops, tool argument schemas, persistent storage, networking, distributed execution, or multi-agent coordination. These omissions are intentional for v0.1.0.
