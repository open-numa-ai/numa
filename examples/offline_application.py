"""Run the complete provider-neutral Numa path without a network service."""

from numa import (
    AgentRuntime,
    AgentStep,
    EventBus,
    EventSpanHandler,
    InMemoryEventHandler,
    InMemorySpanExporter,
    LLMAgent,
    SequentialWorkflow,
    Task,
    ToolAllowlistPolicy,
)
from numa.providers import EchoModelProvider, InstrumentedModelProvider
from numa.tools import AddTool


def main() -> None:
    events = InMemoryEventHandler()
    spans = InMemorySpanExporter()
    bus = EventBus([events, EventSpanHandler(spans)])
    provider = InstrumentedModelProvider(EchoModelProvider(), bus)
    runtime = AgentRuntime(event_bus=bus, tool_permission_policy=ToolAllowlistPolicy(["add"]))
    runtime.register_tool(AddTool())
    workflow = SequentialWorkflow([AgentStep(LLMAgent(provider), name="answer")])

    result = workflow.run(runtime, Task(description="Hello from the offline application"))
    print(result.final_message.content if result.final_message else "no result")
    print(runtime.execute_tool("add", left=2, right=3))
    print(f"events={len(events.events)} spans={len(spans.spans)}")


if __name__ == "__main__":
    main()
