from __future__ import annotations

import asyncio

import pytest

from numa.agents import Agent, AsyncAgent
from numa.core import (
    AgentExecutionError,
    Context,
    Message,
    MessageRole,
    Task,
    TaskNotFoundError,
    TaskResumeError,
    TaskStatus,
)
from numa.runtime import AgentRuntime, AsyncAgentRuntime
from numa.tasks import InMemoryTaskStore, TaskRecord


class CountingAgent(Agent):
    def __init__(self, name: str = "counting") -> None:
        self._name = name
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    def run(self, task: Task, context: Context) -> Message:
        self.calls += 1
        return Message(
            role=MessageRole.ASSISTANT,
            content=f"{task.description}:{len(context.messages)}",
        )


class FailingAgent(Agent):
    @property
    def name(self) -> str:
        return "failing"

    def run(self, task: Task, context: Context) -> Message:
        del task, context
        raise ValueError("persisted failure")


class BlockingAsyncAgent(AsyncAgent):
    def __init__(self, started: asyncio.Event, release: asyncio.Event) -> None:
        self.started = started
        self.release = release
        self.calls = 0

    @property
    def name(self) -> str:
        return "blocking"

    async def run(self, task: Task, context: Context) -> Message:
        del context
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return Message(role=MessageRole.ASSISTANT, content=task.description)


def test_runtime_persists_completed_task_and_context() -> None:
    store = InMemoryTaskStore()
    runtime = AgentRuntime(task_store=store)
    task = Task(description="run")
    context = Context(metadata={"session": "one"})

    result = runtime.run(CountingAgent(), task, context)
    record = store.load(task.id)

    assert record is not None
    assert record.task.status is TaskStatus.COMPLETED
    assert record.task.result == result
    assert record.context.messages == [result]
    assert record.context.metadata == {"session": "one"}


def test_runtime_persists_failed_task_before_wrapping_error() -> None:
    store = InMemoryTaskStore()
    task = Task(description="fail")

    with pytest.raises(AgentExecutionError):
        AgentRuntime(task_store=store).run(FailingAgent(), task)

    record = store.load(task.id)
    assert record is not None
    assert record.task.status is TaskStatus.FAILED
    assert record.task.error == "persisted failure"
    assert record.task.result is None


def test_runtime_returns_completed_result_without_rerunning() -> None:
    store = InMemoryTaskStore()
    original_agent = CountingAgent()
    task = Task(description="once")
    AgentRuntime(task_store=store).run(original_agent, task)
    resumed_agent = CountingAgent()

    result = AgentRuntime(task_store=store).resume(resumed_agent, task.id)

    assert result.content == "once:0"
    assert original_agent.calls == 1
    assert resumed_agent.calls == 0


@pytest.mark.parametrize("status", [TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.FAILED])
def test_runtime_resumes_unfinished_task_with_same_identity(status: TaskStatus) -> None:
    store = InMemoryTaskStore()
    task = Task(
        description="resume",
        id="stable-id",
        status=status,
        error="interrupted",
    )
    context = Context(
        messages=[Message(role=MessageRole.USER, content="existing")],
    )
    store.save(TaskRecord(agent_name="counting", task=task, context=context))

    result = AgentRuntime(task_store=store).resume(CountingAgent(), task.id)
    record = store.load(task.id)

    assert result.content == "resume:1"
    assert record is not None
    assert record.task.id == "stable-id"
    assert record.task.status is TaskStatus.COMPLETED
    assert record.task.error is None
    assert [message.content for message in record.context.messages] == ["existing", "resume:1"]


def test_runtime_rejects_missing_store_task_and_agent_mismatch() -> None:
    with pytest.raises(TaskResumeError, match="TaskStore"):
        AgentRuntime().resume(CountingAgent(), "missing")

    store = InMemoryTaskStore()
    store.save(
        TaskRecord(
            agent_name="owner",
            task=Task(description="owned"),
            context=Context(),
        )
    )
    record = store.list()[0]

    with pytest.raises(TaskResumeError, match="belongs to Agent"):
        AgentRuntime(task_store=store).resume(CountingAgent(), record.task.id)
    with pytest.raises(TaskNotFoundError, match="not persisted"):
        AgentRuntime(task_store=store).resume(CountingAgent(), "missing")


def test_async_runtime_persists_cancellation_and_resumes() -> None:
    async def scenario() -> None:
        store = InMemoryTaskStore()
        started = asyncio.Event()
        release = asyncio.Event()
        agent = BlockingAsyncAgent(started, release)
        task = Task(description="continue")
        runtime = AsyncAgentRuntime(task_store=store)
        execution = asyncio.create_task(runtime.run(agent, task))
        await started.wait()
        execution.cancel()
        with pytest.raises(asyncio.CancelledError):
            await execution

        cancelled = store.load(task.id)
        assert cancelled is not None
        assert cancelled.task.status is TaskStatus.CANCELLED

        release.set()
        result = await runtime.resume(agent, task.id)
        resumed = store.load(task.id)

        assert result.content == "continue"
        assert agent.calls == 2
        assert resumed is not None
        assert resumed.task.status is TaskStatus.COMPLETED
        assert resumed.task.error is None

    asyncio.run(scenario())
