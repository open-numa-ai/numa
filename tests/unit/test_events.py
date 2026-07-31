import pytest

from numa.agents import Agent, EchoAgent
from numa.core import (
    AgentExecutionError,
    Context,
    Message,
    MessageRole,
    Task,
    ToolValidationError,
)
from numa.events import Event, EventBus, EventHandler, EventType, InMemoryEventHandler
from numa.providers import (
    EchoModelProvider,
    InstrumentedModelProvider,
    ModelProviderExecutionError,
    ModelRequest,
)
from numa.runtime import AgentRuntime
from numa.tools import AddTool


class FailingEventHandler(EventHandler):
    def handle(self, event: Event) -> None:
        del event
        raise RuntimeError("handler failed")


class FailingAgent(Agent):
    @property
    def name(self) -> str:
        return "failing"

    def run(self, task: Task, context: Context) -> Message:
        del task, context
        raise ValueError("agent failed")


def event_types(handler: InMemoryEventHandler) -> list[EventType]:
    return [event.type for event in handler.events]


def test_event_bus_isolates_handler_failures() -> None:
    collector = InMemoryEventHandler()
    bus = EventBus([FailingEventHandler(), collector])
    event = Event(
        type=EventType.AGENT_STARTED,
        execution_id="execution",
        component_name="agent",
    )

    bus.emit(event)

    assert collector.events == (event,)


def test_runtime_emits_correlated_agent_events() -> None:
    collector = InMemoryEventHandler()
    task = Task(description="hello")

    AgentRuntime(event_bus=EventBus([collector])).run(EchoAgent(), task)

    assert event_types(collector) == [EventType.AGENT_STARTED, EventType.AGENT_COMPLETED]
    assert {event.execution_id for event in collector.events} == {task.id}
    assert {event.component_name for event in collector.events} == {"example_agent"}


def test_runtime_emits_agent_failure_without_changing_exception() -> None:
    collector = InMemoryEventHandler()

    with pytest.raises(AgentExecutionError):
        AgentRuntime(event_bus=EventBus([collector])).run(
            FailingAgent(),
            Task(description="fail"),
        )

    assert event_types(collector) == [EventType.AGENT_STARTED, EventType.AGENT_FAILED]
    assert collector.events[-1].metadata == {"error_type": "ValueError"}


def test_runtime_emits_correlated_tool_events() -> None:
    collector = InMemoryEventHandler()
    runtime = AgentRuntime(event_bus=EventBus([collector]))
    runtime.register_tool(AddTool())

    assert runtime.execute_tool("add", left=2, right=3) == {"result": 5}

    assert event_types(collector) == [EventType.TOOL_STARTED, EventType.TOOL_COMPLETED]
    assert len({event.execution_id for event in collector.events}) == 1
    assert {event.component_name for event in collector.events} == {"add"}


def test_runtime_emits_tool_validation_failure() -> None:
    collector = InMemoryEventHandler()
    runtime = AgentRuntime(event_bus=EventBus([collector]))
    runtime.register_tool(AddTool())

    with pytest.raises(ToolValidationError):
        runtime.execute_tool("add", left="invalid", right=3)

    assert event_types(collector) == [EventType.TOOL_STARTED, EventType.TOOL_FAILED]
    assert collector.events[-1].metadata == {"error_type": "ToolValidationError"}


def test_instrumented_provider_emits_correlated_events() -> None:
    collector = InMemoryEventHandler()
    provider = InstrumentedModelProvider(EchoModelProvider(), EventBus([collector]))
    request = ModelRequest(
        messages=(Message(role=MessageRole.USER, content="secret prompt"),),
        model="echo-test",
        metadata={"execution_id": "task-123", "private": "not-an-event"},
    )

    response = provider.generate(request)

    assert response.message.content == "secret prompt"
    assert event_types(collector) == [
        EventType.PROVIDER_STARTED,
        EventType.PROVIDER_COMPLETED,
    ]
    assert {event.execution_id for event in collector.events} == {"task-123"}
    assert all(event.metadata == {"model": "echo-test"} for event in collector.events)


def test_instrumented_provider_preserves_failure() -> None:
    collector = InMemoryEventHandler()
    provider = InstrumentedModelProvider(EchoModelProvider(), EventBus([collector]))

    with pytest.raises(ModelProviderExecutionError):
        provider.generate(ModelRequest(messages=()))

    assert event_types(collector) == [EventType.PROVIDER_STARTED, EventType.PROVIDER_FAILED]
    assert collector.events[-1].metadata["error_type"] == "ModelProviderExecutionError"


def test_in_memory_handler_returns_snapshot() -> None:
    collector = InMemoryEventHandler()
    snapshot = collector.events
    collector.handle(
        Event(
            type=EventType.TOOL_STARTED,
            execution_id="execution",
            component_name="tool",
            metadata={"value": 1},
        )
    )

    assert snapshot == ()
    assert len(collector.events) == 1
