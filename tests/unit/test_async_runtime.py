from __future__ import annotations

import asyncio

import pytest

from numa.agents import AsyncAgent, AsyncEchoAgent
from numa.core import (
    AgentExecutionError,
    Context,
    Message,
    MessageRole,
    Task,
    TaskStatus,
    ToolValidationError,
)
from numa.events import EventBus, EventType, InMemoryEventHandler
from numa.runtime import AsyncAgentRuntime
from numa.tools import AsyncAddTool


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