from __future__ import annotations

import asyncio

import pytest

from numa.agents import AsyncAgent, AsyncEchoAgent
from numa.core import (
    AgentExecutionError,
    AgentTimeoutError,
    Context,
    Message,
    MessageRole,
    Task,
    TaskStatus,
    ToolValidationError,
    ToolTimeoutError,
)
from numa.events import EventBus, EventType, InMemoryEventHandler
from numa.runtime import AsyncAgentRuntime, ResiliencePolicy, RetryPolicy
from numa.tools import AsyncAddTool, AsyncTool


class FailingAsyncAgent(AsyncAgent):
    @property
    def name(self) -> str:
        return "failing_async"

    async def run(self, task: Task, context: Context) -> Message:
        del task, context
        raise ValueError("async agent failed")


class CoordinatedAgent(AsyncAgent):
    def __init__(self, started: list[str], release: asyncio.Event) -> None:
        self._started = started
        self._release = release

    @property
    def name(self) -> str:
        return "coordinated"

    async def run(self, task: Task, context: Context) -> Message:
        del context
        self._started.append(task.description)
        if len(self._started) == 2:
            self._release.set()
        await self._release.wait()
        return Message(role=MessageRole.ASSISTANT, content=task.description)


class ResilientAgent(AsyncAgent):
    def __init__(
        self,
        failures: int = 0,
        started: asyncio.Event | None = None,
        release: asyncio.Event | None = None,
    ) -> None:
        self.failures = failures
        self.started = started
        self.release = release
        self.attempts = 0

    @property
    def name(self) -> str:
        return "resilient"

    async def run(self, task: Task, context: Context) -> Message:
        del context
        self.attempts += 1
        if self.started is not None:
            self.started.set()
        if self.attempts <= self.failures:
            raise ValueError("retryable failure")
        if self.release is not None:
            await self.release.wait()
        return Message(role=MessageRole.ASSISTANT, content=task.description)


class ResilientTool(AsyncTool):
    def __init__(
        self,
        failures: int = 0,
        started: asyncio.Event | None = None,
        release: asyncio.Event | None = None,
    ) -> None:
        self.failures = failures
        self.started = started
        self.release = release
        self.attempts = 0

    @property
    def name(self) -> str:
        return "resilient_tool"

    async def execute(self, **arguments: object) -> int:
        del arguments
        self.attempts += 1
        if self.started is not None:
            self.started.set()
        if self.attempts <= self.failures:
            raise ValueError("retryable failure")
        if self.release is not None:
            await self.release.wait()
        return self.attempts


def test_async_runtime_completes_task_and_updates_context() -> None:
    async def scenario() -> None:
        task = Task(description="echo this")
        context = Context()

        result = await AsyncAgentRuntime().run(AsyncEchoAgent(), task, context)

        assert result.content == "echo this"
        assert task.status is TaskStatus.COMPLETED
        assert task.result is result
        assert context.messages == [result]

    asyncio.run(scenario())


def test_async_runtime_wraps_agent_errors_and_emits_events() -> None:
    async def scenario() -> None:
        collector = InMemoryEventHandler()
        task = Task(description="fail")
        runtime = AsyncAgentRuntime(event_bus=EventBus([collector]))

        with pytest.raises(AgentExecutionError, match="failing_async"):
            await runtime.run(FailingAsyncAgent(), task)

        assert task.status is TaskStatus.FAILED
        assert task.error == "async agent failed"
        assert [event.type for event in collector.events] == [
            EventType.AGENT_STARTED,
            EventType.AGENT_FAILED,
        ]
        assert {event.execution_id for event in collector.events} == {task.id}
        assert collector.events[-1].metadata == {"error_type": "ValueError"}

    asyncio.run(scenario())


def test_async_runtime_validates_and_executes_tool() -> None:
    async def scenario() -> None:
        collector = InMemoryEventHandler()
        runtime = AsyncAgentRuntime(event_bus=EventBus([collector]))
        runtime.register_tool(AsyncAddTool())

        assert await runtime.execute_tool("async_add", left=2, right=3) == {"result": 5}
        with pytest.raises(ToolValidationError):
            await runtime.execute_tool("async_add", left="invalid", right=3)

        assert [event.type for event in collector.events] == [
            EventType.TOOL_STARTED,
            EventType.TOOL_COMPLETED,
            EventType.TOOL_STARTED,
            EventType.TOOL_FAILED,
        ]

    asyncio.run(scenario())


def test_gather_runs_agents_concurrently_and_preserves_order() -> None:
    async def scenario() -> None:
        started: list[str] = []
        release = asyncio.Event()
        agent = CoordinatedAgent(started, release)
        first = Task(description="first")
        second = Task(description="second")

        results = await AsyncAgentRuntime().gather((agent, first), (agent, second))

        assert started == ["first", "second"]
        assert [result.content for result in results] == ["first", "second"]
        assert first.status is TaskStatus.COMPLETED
        assert second.status is TaskStatus.COMPLETED

    asyncio.run(scenario())


def test_async_runtime_retries_agent_before_completing() -> None:
    async def scenario() -> None:
        collector = InMemoryEventHandler()
        policy = ResiliencePolicy(retry=RetryPolicy(max_attempts=3))
        runtime = AsyncAgentRuntime(event_bus=EventBus([collector]))
        agent = ResilientAgent(failures=2)
        task = Task(description="eventually succeeds")

        result = await runtime.run(agent, task, resilience_policy=policy)

        assert result.content == "eventually succeeds"
        assert agent.attempts == 3
        assert [event.type for event in collector.events] == [
            EventType.AGENT_STARTED,
            EventType.AGENT_COMPLETED,
        ]

    asyncio.run(scenario())


def test_async_runtime_times_out_agent_across_retry_budget() -> None:
    async def scenario() -> None:
        collector = InMemoryEventHandler()
        policy = ResiliencePolicy(timeout_seconds=0.01)
        runtime = AsyncAgentRuntime(event_bus=EventBus([collector]))
        task = Task(description="never completes")

        with pytest.raises(AgentTimeoutError):
            await runtime.run(
                ResilientAgent(release=asyncio.Event()),
                task,
                resilience_policy=policy,
            )

        assert task.status is TaskStatus.FAILED
        assert collector.events[-1].type is EventType.AGENT_FAILED
        assert collector.events[-1].metadata == {"error_type": "AgentTimeoutError"}

    asyncio.run(scenario())


def test_async_runtime_cancellation_is_not_retried() -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        agent = ResilientAgent(started=started, release=asyncio.Event())
        collector = InMemoryEventHandler()
        policy = ResiliencePolicy(retry=RetryPolicy(max_attempts=3))
        task = Task(description="cancel me")
        execution = asyncio.create_task(
            AsyncAgentRuntime(event_bus=EventBus([collector])).run(
                agent,
                task,
                resilience_policy=policy,
            )
        )
        await started.wait()

        execution.cancel()
        with pytest.raises(asyncio.CancelledError):
            await execution

        assert agent.attempts == 1
        assert task.status is TaskStatus.CANCELLED
        assert [event.type for event in collector.events] == [
            EventType.AGENT_STARTED,
            EventType.AGENT_CANCELLED,
        ]

    asyncio.run(scenario())


def test_async_runtime_applies_retry_and_timeout_to_tools() -> None:
    async def scenario() -> None:
        retrying_tool = ResilientTool(failures=1)
        runtime = AsyncAgentRuntime()
        runtime.register_tool(retrying_tool)
        retry_policy = ResiliencePolicy(retry=RetryPolicy(max_attempts=2))

        result = await runtime.execute_tool_with_policy(
            "resilient_tool",
            retry_policy,
        )

        assert result == 2
        assert retrying_tool.attempts == 2

        waiting_tool = ResilientTool(release=asyncio.Event())
        runtime.register_tool(waiting_tool)
        with pytest.raises(ToolTimeoutError):
            await runtime.execute_tool_with_policy(
                "resilient_tool",
                ResiliencePolicy(timeout_seconds=0.01),
            )

    asyncio.run(scenario())


def test_async_runtime_emits_tool_cancellation() -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        tool = ResilientTool(started=started, release=asyncio.Event())
        collector = InMemoryEventHandler()
        runtime = AsyncAgentRuntime(event_bus=EventBus([collector]))
        runtime.register_tool(tool)
        execution = asyncio.create_task(runtime.execute_tool("resilient_tool"))
        await started.wait()

        execution.cancel()
        with pytest.raises(asyncio.CancelledError):
            await execution

        assert tool.attempts == 1
        assert [event.type for event in collector.events] == [
            EventType.TOOL_STARTED,
            EventType.TOOL_CANCELLED,
        ]

    asyncio.run(scenario())
