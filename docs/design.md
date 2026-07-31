# Design

Numa's API design favors explicit data flow, narrow interfaces, and replaceable adapters.

## API Principles

- Public methods should have one clear responsibility.
- Core models should remain independent of providers and persistence.
- Runtime policy should not leak into agent implementations.
- Framework exceptions should preserve original exception causes.
- Defaults should support local examples without limiting production adapters.

## Core Contracts

### Agent

Receives a `Task` and `Context`, then returns a `Message`. Provider clients and prompting policy belong to concrete agents.

### Runtime

Owns execution lifecycle, dependency access, logging, and error conversion. The initial runtime is intentionally synchronous.

### Tool

Exposes a named capability. Future layers can add schemas, authorization, isolation, retries, and telemetry without expanding the base contract prematurely.

### Memory

Defines basic storage behavior independently of a database. Search, vector retrieval, and transactional interfaces should be added as specialized contracts when required.

### Configuration

Loads immutable settings with deterministic precedence. Secrets should enter through environment variables or an external secret manager, not committed files.

## Compatibility Policy

During the v0.x series, APIs may evolve as integrations reveal missing requirements. Changes should remain focused, documented, typed, and covered by tests. Deprecation paths become mandatory before v1.0.

## Non-Goals for v0.1.0

- LLM provider integrations
- Prompt or planning frameworks
- Autonomous execution loops
- Persistent or vector memory
- Distributed and asynchronous execution
- Multi-agent routing
