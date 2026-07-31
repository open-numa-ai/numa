# Structured Events

Numa emits provider-neutral lifecycle events so applications can add logs, metrics, traces, or audit sinks without coupling execution code to an observability vendor.

## Event Model

Every `Event` contains:

- A stable `EventType`
- A unique event ID
- An execution ID shared by related lifecycle transitions
- A component name
- A UTC timestamp
- Structured metadata

Built-in event types cover Agent, Tool, and Provider started, completed, and failed transitions.

Numa does not include task descriptions, prompts, model parameters, tool arguments, or results in built-in events. Custom handlers remain responsible for protecting any metadata they add.

## Collect Events

Attach handlers to an `EventBus` and pass the bus into the Runtime:

```python
from numa import AgentRuntime, EventBus, InMemoryEventHandler, Task
from numa.agents import EchoAgent

collector = InMemoryEventHandler()
runtime = AgentRuntime(event_bus=EventBus([collector]))
runtime.run(EchoAgent(), Task(description="Hello"))

for event in collector.events:
    print(event.type.value, event.execution_id, event.component_name)
```

`InMemoryEventHandler.events` returns an immutable snapshot. It is intended for tests and local inspection, not durable telemetry storage.

## Instrument Providers

Provider instrumentation uses a decorator so existing and third-party adapters do not need to change:

```python
from numa import EventBus, InMemoryEventHandler, Message, MessageRole, ModelRequest
from numa.providers import EchoModelProvider, InstrumentedModelProvider

collector = InMemoryEventHandler()
provider = InstrumentedModelProvider(EchoModelProvider(), EventBus([collector]))
provider.generate(
    ModelRequest(
        messages=(Message(role=MessageRole.USER, content="Hello"),),
        metadata={"execution_id": "task-123"},
    )
)
```

When `execution_id` is a non-empty string in request metadata, Provider events inherit it. Otherwise the decorator creates a new ID.

## Custom Handlers

Implement `EventHandler.handle()` to integrate an observability backend:

```python
from numa import Event, EventHandler


class MetricsHandler(EventHandler):
    def handle(self, event: Event) -> None:
        print(event.type.value)
```

`EventBus` isolates handler failures. One broken handler does not interrupt Agent, Tool, or Provider execution and does not prevent later handlers from receiving the event. Handler failures are logged through Numa's standard logger.

## Current Boundaries

The event layer is synchronous and in-process. It does not provide durable queues, distributed context propagation, sampling, spans, exporters, or OpenTelemetry integration. Those capabilities can be implemented by handlers or future adapters without changing lifecycle producers.