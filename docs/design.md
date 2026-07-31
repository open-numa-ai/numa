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

Exposes a named capability with Pydantic input and optional output schemas. Future layers can add authorization, isolation, retries, and telemetry without expanding the base contract prematurely.

### Memory

Defines basic storage behavior independently of a database. The SQLite adapter provides JSON persistence while search, vector retrieval, and transactional interfaces remain specialized future contracts.

### Model Provider

Translates provider-neutral requests and responses at vendor SDK boundaries. Agent prompting and orchestration policy remain outside the provider contract.

### Events

Expose synchronous lifecycle hooks without coupling producers to observability vendors. Event handlers are failure-isolated and built-in events avoid request or response payloads.

### Configuration

Loads immutable settings with deterministic precedence. Secrets should enter through environment variables or an external secret manager, not committed files.

## Compatibility Policy

During the v0.x series, APIs may evolve as integrations reveal missing requirements. Changes should remain focused, documented, typed, and covered by tests. Deprecation paths become mandatory before v1.0.

## Current Non-Goals

- Bundled vendor LLM adapters
- Prompt or planning frameworks
- Autonomous execution loops
- Vector memory and retrieval
- Distributed and asynchronous execution
- Multi-agent routing
