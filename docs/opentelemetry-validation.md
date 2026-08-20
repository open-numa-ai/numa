# OpenTelemetry adapter validation

Numa's optional OpenTelemetry reference adapter validates that provider-neutral
`SpanRecord` values can be exported through an application-owned
OpenTelemetry tracer. The adapter stays under `examples/adapters`; neither
`opentelemetry-api` nor `opentelemetry-sdk` is a Numa core dependency.

## Mapping

Each Numa lifecycle transition becomes one short OpenTelemetry span. The
adapter does not keep spans open between `started` and `completed`, and it does
not reconstruct parent/child relationships between separate Numa events. If
the application already has an active OpenTelemetry context, normal tracer
context propagation may still attach the transition span to that context.

| Numa value | OpenTelemetry value |
| --- | --- |
| `SpanRecord.name` | span name |
| `execution_id` | `numa.execution.id` |
| `component_name` | `numa.component.name` |
| `component_type` | `numa.component.type` |
| lifecycle status | `numa.lifecycle.status` |
| event metadata | `numa.metadata.<key>` |
| `failed` status | OpenTelemetry `ERROR` status |

`started`, `completed`, and `cancelled` transitions leave OpenTelemetry status
unset. OpenTelemetry recommends leaving successful spans unset unless an
explicit `OK` status is necessary. Unsupported attribute values, including
nested mappings, empty sequences, and mixed-type sequences, are dropped rather
than stringified.

## Local SDK validation

Run the in-memory SDK example without changing project dependencies:

```bash
uv run --with opentelemetry-sdk \
  python examples/opentelemetry_observability.py
```

The example configures an SDK `TracerProvider`, a `SimpleSpanProcessor`, and an
SDK in-memory exporter. A real application can inject a provider configured
with an OTLP or another OpenTelemetry SDK exporter instead.

The adapter can also be composed directly:

```python
from examples.adapters.opentelemetry_spans import create_opentelemetry_exporter
from numa import AgentRuntime, EventBus, EventSpanHandler

exporter = create_opentelemetry_exporter()
runtime = AgentRuntime(event_bus=EventBus([EventSpanHandler(exporter)]))
```

Calling `create_opentelemetry_exporter()` requires the OpenTelemetry API. Tests
can inject a structural tracer directly into `OpenTelemetrySpanExporter`
without installing the SDK.

## Privacy and operational boundaries

Numa's built-in lifecycle events do not contain prompts, model responses,
normalized Tool arguments, audio bytes, or transcripts. The reference adapter
adds no payload capture. It does forward supported event metadata, so
applications that emit custom metadata remain responsible for redaction,
sampling, batching, retention, and backend configuration.

`EventBus` invokes handlers synchronously and isolates their exceptions from
Runtime execution. For production workloads, configure an appropriate SDK
span processor and exporter rather than performing slow network work in the
Numa adapter.

## Validation boundaries

Offline contract tests verify attribute mapping, failed status conversion,
unsupported-value filtering, span cleanup, missing dependency errors, Runtime
composition, and payload exclusion. The in-memory SDK example validates SDK
interoperability; it does not validate an external collector, OTLP transport,
backend ingestion, sampling policy, or production throughput.
