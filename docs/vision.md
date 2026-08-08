# Vision

Numa exists to provide a small, understandable runtime foundation for Python agent applications.

Agent applications need model access, execution lifecycle, tools, state, and observability. When these concerns are tightly coupled, prototypes become difficult to test and expensive to evolve.

Numa provides provider-neutral contracts and local runtime infrastructure for these boundaries. Teams retain control over model vendors, prompts, planning, storage, deployment, and product behavior.

## What Numa Is

Numa is an embeddable, open-source Python runtime foundation built around:

- Explicit agent and task abstractions
- Synchronous and asynchronous component execution
- Replaceable model, Tool, memory, and Task Store adapters
- Inspectable lifecycle, failure, permission, and persistence behavior
- Typed boundaries that applications can compose without adopting a full stack

## What Numa Is Not

Numa is not an LLM SDK, prompt or planning framework, hosted agent platform, distributed worker system, or opinionated end-user application. It does not currently provide autonomous loops or multi-agent coordination.

The framework should not hide provider behavior behind magic or force applications into one model, storage, planning, or deployment approach. Future capabilities should be added only when they preserve this boundary and are supported by concrete integration requirements.

## Framework Principles

- Keep the smallest useful public interfaces.
- Make execution state and failures inspectable.
- Prefer composition over inheritance beyond base contracts.
- Keep infrastructure replaceable at explicit boundaries.
- Protect backward compatibility as the project matures.
- Treat security, privacy, and observability as architecture concerns.
- Keep application strategy outside the base Runtime.
