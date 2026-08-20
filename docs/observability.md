# Observability bridge

Numa emits synchronous, provider-neutral lifecycle `Event` objects. The core
package includes `EventSpanHandler`, which converts each event into a
`SpanRecord` and sends it to an injected `SpanExporter`. No tracing SDK is a
core dependency.

```python
from numa import AgentRuntime, EventBus, EventSpanHandler, InMemorySpanExporter

exporter = InMemorySpanExporter()
runtime = AgentRuntime(event_bus=EventBus([EventSpanHandler(exporter)]))
```

The bridge exports event type, execution ID, component name, component type,
and event metadata. Prompts, model responses, and normalized Tool arguments
are not part of the lifecycle event contract and are not exported. An
application can implement `SpanExporter` for OpenTelemetry, logs, metrics, or
another backend without changing Runtime code.

See [OpenTelemetry adapter validation](opentelemetry-validation.md) for an
optional examples-layer adapter, offline contract tests, and an SDK in-memory
validation command.

Exporters should be non-blocking or buffered; Event handlers run synchronously
and handler failures are isolated by `EventBus`. Sampling, batching, exporter
configuration, and sensitive metadata redaction remain application concerns.
