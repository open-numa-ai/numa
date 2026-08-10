from __future__ import annotations

from typing import Any

from numa import (
    AgentRuntime,
    AgentStep,
    EventBus,
    EventSpanHandler,
    InMemorySpanExporter,
    InMemoryTaskStore,
    RuntimeMiddleware,
    SequentialWorkflow,
    Task,
    ToolAllowlistPolicy,
)
from numa.agents import LLMAgent
from numa.events import InMemoryEventHandler
from numa.providers import EchoModelProvider, InstrumentedModelProvider
from numa.runtime.middleware import RuntimeInvocation, RuntimeNext
from numa.tools import AddTool


class RecordingMiddleware(RuntimeMiddleware):
    """Record normalized calls without changing their behavior."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def invoke(self, invocation: RuntimeInvocation, call_next: RuntimeNext) -> Any:
        self.calls.append((type(invocation).__name__, invocation.component_name))
        return call_next(invocation)


def test_offline_application_path_exercises_runtime_boundaries() -> None:
    events = InMemoryEventHandler()
    spans = InMemorySpanExporter()
    middleware = RecordingMiddleware()
    provider = InstrumentedModelProvider(
        EchoModelProvider(), EventBus([events, EventSpanHandler(spans)])
    )
    runtime = AgentRuntime(
        event_bus=EventBus([events, EventSpanHandler(spans)]),
        task_store=InMemoryTaskStore(),
        middlewares=[middleware],
        tool_permission_policy=ToolAllowlistPolicy(["add"]),
    )
    runtime.register_tool(AddTool())

    workflow = SequentialWorkflow(
        [
            AgentStep(LLMAgent(provider, name="draft"), name="draft"),
            AgentStep(
                LLMAgent(provider, name="review"),
                name="review",
                task_factory=lambda state: Task(
                    description=f"Review: {state.result('draft').message.content}"
                ),
            ),
        ]
    )
    root = Task(description="Write a release note")
    result = workflow.run(runtime, root)

    assert root.status.value == "completed"
    assert result.final_message is not None
    assert result.result("review").message.content.startswith("Review:")
    assert runtime.execute_tool("add", left=2, right=3) == {"result": 5}
    assert ("AgentInvocation", "draft") in middleware.calls
    assert ("ToolInvocation", "add") in middleware.calls
    assert any(event.type.value == "provider.completed" for event in events.events)
    assert any(span.name == "numa.agent.completed" for span in spans.spans)
    assert any(span.name == "numa.tool.completed" for span in spans.spans)
    assert all("prompt" not in span.attributes for span in spans.spans)
