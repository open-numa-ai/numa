"""Export Numa lifecycle records through an OpenTelemetry SDK provider."""

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from examples.adapters.opentelemetry_spans import create_opentelemetry_exporter
from numa import AgentRuntime, EventBus, EventSpanHandler, Task
from numa.agents import EchoAgent


def main() -> None:
    sdk_exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(sdk_exporter))
    exporter = create_opentelemetry_exporter(tracer_provider=provider)
    runtime = AgentRuntime(event_bus=EventBus([EventSpanHandler(exporter)]))

    result = runtime.run(EchoAgent(), Task(description="Hello from OpenTelemetry"))
    provider.force_flush()
    spans = sdk_exporter.get_finished_spans()

    print(result.content)
    for span in spans:
        print(span.name, dict(span.attributes or {}), span.status.status_code.name)

    provider.shutdown()


if __name__ == "__main__":
    main()
