# Roadmap

Numa evolves from stable framework contracts toward production runtime capabilities. Roadmap items describe direction, not release guarantees.

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

Goal: support larger and concurrent workloads without changing core semantics.

- [x] Async agent and tool contracts
- [x] Cancellation, timeout, and retry policies
- [x] Task persistence and resumability
- [ ] Runtime middleware
- [ ] Security and tool permission policies

## Future

- Planning and workflow composition
- Multi-agent routing and collaboration
- Distributed runtime adapters
- Evaluation and observability integrations

## Guiding Priorities

- Stable and understandable public APIs
- Provider and infrastructure independence
- Security, privacy, and observability
- Focused releases backed by tests and documentation
