# Roadmap

Numa evolves from small framework contracts toward a more capable embeddable runtime. The version labels below group capabilities; they do not correspond to published package versions, release dates, or production-readiness guarantees.

## v0.1: Project Foundation

Goal: establish a small, typed, testable framework core.

- [x] Python 3.11+ `src` package layout
- [x] Agent, task, message, context, tool, and memory contracts
- [x] Synchronous agent runtime
- [x] YAML, JSON, and environment configuration
- [x] Unified logging and CLI foundation
- [x] Ruff, Mypy, Pytest, and GitHub Actions setup

## v0.2: Integration Boundaries

Goal: validate contracts through real but optional adapters.

- [x] Tool input and output schemas
- [x] Plugin discovery through Python entry points
- [x] Persistent memory adapter
- [x] Optional model provider interfaces
- [x] Structured event and tracing hooks

## v0.3: Runtime Evolution

Goal: make local execution more durable and composable without changing core semantics.

- [x] Async agent and tool contracts
- [x] Cancellation, timeout, and retry policies
- [x] Task persistence and resumability
- [x] Runtime middleware
- [x] Security and tool permission policies

## v0.4: Application Composition

Goal: compose explicit local Agent execution without embedding planning strategy in the Runtime.

- [x] Sequential Agent workflows with shared Context
- [x] Conditional workflow branches over completed results
- [x] Structured asynchronous parallel branches
- [x] Deterministic named step results and child Task correlation

## Possible Future Directions

These items are areas to validate through real integrations, not committed features:

- Multi-agent routing and collaboration
- Distributed runtime adapters
- Evaluation and observability integrations

## Guiding Priorities

- Stable and understandable public APIs
- Provider and infrastructure independence
- Security, privacy, and observability
- Focused releases backed by tests and documentation
