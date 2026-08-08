from __future__ import annotations

import asyncio

import pytest

from numa import (
    AsyncAgentRuntime,
    AsyncAgentStep,
    AsyncConditionalWorkflow,
    AsyncParallelWorkflow,
    AsyncSequentialWorkflow,
    Context,
    Message,
    MessageRole,
    Task,
    TaskStatus,
    WorkflowExecutionError,
)
from numa.agents import AsyncAgent


class CoordinatedAgent(AsyncAgent):
    def __init__(self, name: str, started: list[str], release: asyncio.Event) -> None:
        self._name = name
        self._started = started
        self._release = release

    @property
    def name(self) -> str:
        return self._name

    async def run(self, task: Task, context: Context) -> Message:
        self._started.append(self.name)
        if len(self._started) == 2:
            self._release.set()
        await self._release.wait()
        return Message(
            role=MessageRole.ASSISTANT,
            content=f"{self.name}:{task.description}:{len(context.messages)}",
        )


class ImmediateAgent(AsyncAgent):
    def __init__(self, name: str, calls: list[str] | None = None) -> None:
        self._name = name
        self._calls = calls

    @property
    def name(self) -> str:
        return self._name

    async def run(self, task: Task, context: Context) -> Message:
        if self._calls is not None:
            self._calls.append(self.name)
        return Message(
            role=MessageRole.ASSISTANT,
            content=f"{self.name}:{task.description}:{len(context.messages)}",
        )


class FailingAsyncAgent(AsyncAgent):
    @property
    def name(self) -> str:
        return "failing"

    async def run(self, task: Task, context: Context) -> Message:
        del task, context
        await asyncio.sleep(0)
        raise RuntimeError("branch exploded")


class WaitingAgent(AsyncAgent):
    def __init__(self, started: asyncio.Event, cancelled: asyncio.Event) -> None:
        self.started = started
        self.cancelled = cancelled

    @property
    def name(self) -> str:
        return "waiting"

    async def run(self, task: Task, context: Context) -> Message:
        del task, context
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise
        raise AssertionError("unreachable")


def test_async_parallel_workflow_runs_concurrently_and_merges_in_declared_order() -> None:
    async def scenario() -> None:
        started: list[str] = []
        release = asyncio.Event()
        workflow = AsyncParallelWorkflow(
            [
                AsyncAgentStep(CoordinatedAgent("first", started, release)),
                AsyncAgentStep(CoordinatedAgent("second", started, release)),
            ]
        )
        task = Task(description="parallel")
        context = Context(
            messages=[Message(role=MessageRole.USER, content="existing")],
            metadata={"scope": "root"},
        )

        result = await workflow.run(AsyncAgentRuntime(), task, context)

        assert started == ["first", "second"]
        assert [step.name for step in result.steps] == ["first", "second"]
        assert [message.content for message in context.messages] == [
            "existing",
            "first:parallel:1",
            "second:parallel:1",
        ]
        assert task.status is TaskStatus.COMPLETED
        assert task.result is result.result("second").message

    asyncio.run(scenario())


def test_async_sequence_can_follow_parallel_results_and_select_a_branch() -> None:
    async def scenario() -> None:
        calls: list[str] = []
        workflow = AsyncSequentialWorkflow(
            [
                AsyncParallelWorkflow(
                    [
                        AsyncAgentStep(ImmediateAgent("left", calls)),
                        AsyncAgentStep(ImmediateAgent("right", calls)),
                    ]
                ),
                AsyncConditionalWorkflow(
                    lambda state: state.result("left").message.content.startswith("left:"),
                    AsyncAgentStep(
                        ImmediateAgent("merge", calls),
                        task_factory=lambda state: Task(
                            description=" + ".join(
                                (
                                    state.result("left").message.content,
                                    state.result("right").message.content,
                                )
                            )
                        ),
                    ),
                    AsyncAgentStep(ImmediateAgent("fallback", calls)),
                ),
            ]
        )

        result = await workflow.run(AsyncAgentRuntime(), Task(description="compose"))

        assert calls == ["left", "right", "merge"]
        assert [step.name for step in result.steps] == ["left", "right", "merge"]
        assert result.final_message is not None
        assert result.final_message.content.startswith("merge:left:compose:0 + right:compose:0:2")

    asyncio.run(scenario())


def test_parallel_failure_cancels_siblings_and_marks_root_failed() -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        cancelled = asyncio.Event()
        workflow = AsyncParallelWorkflow(
            [
                AsyncAgentStep(WaitingAgent(started, cancelled)),
                AsyncAgentStep(FailingAsyncAgent()),
            ]
        )
        task = Task(description="fail together")

        with pytest.raises(WorkflowExecutionError, match="Parallel workflow branch failed"):
            await workflow.run(AsyncAgentRuntime(), task)

        assert started.is_set()
        assert cancelled.is_set()
        assert task.status is TaskStatus.FAILED
        assert task.result is None

    asyncio.run(scenario())


def test_async_workflow_cancellation_marks_root_cancelled() -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        cancelled = asyncio.Event()
        task = Task(description="cancel")
        execution = asyncio.create_task(
            AsyncAgentStep(WaitingAgent(started, cancelled)).run(AsyncAgentRuntime(), task)
        )
        await started.wait()

        execution.cancel()
        with pytest.raises(asyncio.CancelledError):
            await execution

        assert cancelled.is_set()
        assert task.status is TaskStatus.CANCELLED
        assert task.error == "Workflow execution cancelled"

    asyncio.run(scenario())
