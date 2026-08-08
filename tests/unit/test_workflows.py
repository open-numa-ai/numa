from __future__ import annotations

from typing import cast

import pytest

from numa import (
    AgentRuntime,
    AgentStep,
    ConditionalWorkflow,
    Context,
    Message,
    MessageRole,
    SequentialWorkflow,
    Task,
    TaskStatus,
    WorkflowExecutionError,
    WorkflowTaskFactory,
)
from numa.agents import Agent
from numa.events import EventBus, EventType, InMemoryEventHandler


class RecordingAgent(Agent):
    def __init__(self, name: str, calls: list[str]) -> None:
        self._name = name
        self._calls = calls

    @property
    def name(self) -> str:
        return self._name

    def run(self, task: Task, context: Context) -> Message:
        self._calls.append(self.name)
        return Message(
            role=MessageRole.ASSISTANT,
            content=f"{self.name}:{task.description}:{len(context.messages)}",
        )


class FailingAgent(Agent):
    @property
    def name(self) -> str:
        return "failing"

    def run(self, task: Task, context: Context) -> Message:
        del task, context
        raise RuntimeError("step exploded")


def test_sequential_workflow_shares_context_and_builds_tasks_from_state() -> None:
    calls: list[str] = []
    first = RecordingAgent("first_agent", calls)
    second = RecordingAgent("second_agent", calls)
    workflow = SequentialWorkflow(
        [
            AgentStep(first, name="first"),
            AgentStep(
                second,
                name="second",
                task_factory=lambda state: Task(
                    description=f"summarize {state.result('first').message.content}"
                ),
            ),
        ]
    )
    task = Task(description="root request", metadata={"tenant": "demo"})
    context = Context()

    result = workflow.run(AgentRuntime(), task, context)

    assert calls == ["first_agent", "second_agent"]
    assert [step.name for step in result.steps] == ["first", "second"]
    assert result.result("first").message.content == "first_agent:root request:0"
    assert result.final_message is result.result("second").message
    assert result.final_message.content == "second_agent:summarize first_agent:root request:0:1"
    assert context.messages == [step.message for step in result.steps]
    assert task.status is TaskStatus.COMPLETED
    assert task.result is result.final_message
    assert task.error is None
    assert result.result("first").task.metadata == {
        "tenant": "demo",
        "workflow_id": task.id,
        "workflow_step": "first",
    }


def test_conditional_workflow_uses_prior_results_and_only_runs_selected_branch() -> None:
    calls: list[str] = []
    workflow = SequentialWorkflow(
        [
            AgentStep(RecordingAgent("inspect", calls), name="inspect"),
            ConditionalWorkflow(
                lambda state: state.result("inspect").message.content.startswith("inspect:"),
                AgentStep(RecordingAgent("accepted", calls), name="accepted"),
                AgentStep(RecordingAgent("rejected", calls), name="rejected"),
            ),
        ]
    )

    result = workflow.run(AgentRuntime(), Task(description="check"))

    assert calls == ["inspect", "accepted"]
    assert [step.name for step in result.steps] == ["inspect", "accepted"]
    with pytest.raises(KeyError):
        result.result("rejected")


def test_workflow_steps_keep_runtime_events() -> None:
    collector = InMemoryEventHandler()
    runtime = AgentRuntime(event_bus=EventBus([collector]))
    workflow = SequentialWorkflow(
        [
            AgentStep(RecordingAgent("one", [])),
            AgentStep(RecordingAgent("two", [])),
        ]
    )

    workflow.run(runtime, Task(description="events"))

    assert [event.type for event in collector.events] == [
        EventType.AGENT_STARTED,
        EventType.AGENT_COMPLETED,
        EventType.AGENT_STARTED,
        EventType.AGENT_COMPLETED,
    ]


def test_workflow_wraps_step_failure_and_marks_root_task_failed() -> None:
    task = Task(description="fail")
    workflow = AgentStep(FailingAgent(), name="danger")

    with pytest.raises(WorkflowExecutionError, match="'danger' failed") as captured:
        workflow.run(AgentRuntime(), task)

    assert task.status is TaskStatus.FAILED
    assert task.result is None
    assert task.error == "Workflow step 'danger' failed"
    assert captured.value.__cause__ is not None


def test_workflow_rejects_duplicate_or_empty_step_names() -> None:
    agent = RecordingAgent("agent", [])

    with pytest.raises(ValueError, match="non-empty"):
        AgentStep(agent, name="")
    with pytest.raises(ValueError, match="Duplicate"):
        SequentialWorkflow(
            [
                AgentStep(agent, name="same"),
                AgentStep(agent, name="same"),
            ]
        )


def test_workflow_rejects_invalid_task_factory_result_before_agent_call() -> None:
    calls: list[str] = []
    workflow = AgentStep(
        RecordingAgent("agent", calls),
        task_factory=cast(WorkflowTaskFactory, lambda state: "not a task"),
    )

    with pytest.raises(WorkflowExecutionError, match="Workflow execution failed"):
        workflow.run(AgentRuntime(), Task(description="invalid factory"))

    assert calls == []
