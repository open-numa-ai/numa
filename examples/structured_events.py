"""Inspect structured Agent and Provider lifecycle events."""

from numa import AgentRuntime, EventBus, InMemoryEventHandler, Message, MessageRole, Task
from numa.agents import EchoAgent
from numa.providers import EchoModelProvider, InstrumentedModelProvider, ModelRequest


def main() -> None:
    """Collect correlated events without external observability services."""
    collector = InMemoryEventHandler()
    event_bus = EventBus([collector])

    runtime = AgentRuntime(event_bus=event_bus)
    runtime.run(EchoAgent(), Task(description="Hello from Numa"))

    provider = InstrumentedModelProvider(EchoModelProvider(), event_bus)
    provider.generate(
        ModelRequest(
            messages=(Message(role=MessageRole.USER, content="Hello"),),
            metadata={"execution_id": "example-provider-call"},
        )
    )

    for event in collector.events:
        print(event.type.value, event.execution_id, event.component_name)


if __name__ == "__main__":
    main()
