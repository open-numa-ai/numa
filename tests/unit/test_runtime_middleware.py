from __future__ import annotations

import asyncio
from typing import Any

import pytest

from numa import (
    AgentInvocation,
    AgentRuntime,
    AsyncAgent,
    AsyncAgentRuntime,
    AsyncRuntimeMiddleware,
    AsyncRuntimeNext,
    Context,
    Message,
    MessageRole,
    ResiliencePolicy,
    RetryPolicy,
    RuntimeInvocation,
    RuntimeMiddleware,
    RuntimeNext,
    Task,
    ToolInvocation,
)
from numa.agents import AsyncEchoAgent, EchoAgent
from numa.core import AgentExecutionError
from numa.tools import AddTool, AsyncAddTool


class RecordingMiddleware(RuntimeMiddleware):
    def __init__(self, name: str, calls: list[str]) -> None:
        self.name = name
        self.calls = calls

    def invoke(self, invocation: RuntimeInvocation, call_next: RuntimeNext) -> Any:
        self.calls.append(f"{self.name}:before:{invocation.component_name}")
        invocation.metadata[self.name] = True
        result = call_next(invocation)
        assert invocation.metadata[self.name] is True
        self.calls.append(f"{self.name}:after:{invocation.component_name}")
        return result


class IncrementToolArgumentMiddleware(RuntimeMiddleware):
    def invoke(self, invocation: RuntimeInvocation, call_next: RuntimeNext) -> Any:
        if isinstance(invocation, ToolInvocation):
            invocation.arguments["left"] += 1
        return call_next(invocation)


class ShortCircuitAgentMiddleware(RuntimeMiddleware):
    def invoke(self, invocation: RuntimeInvocation, call_next: RuntimeNext) -> Any:
        del call_next
        if isinstance(invocation, AgentInvocation):
            return Message(role=MessageRole.ASSISTANT, content="from middleware")
        raise AssertionError("expected an Agent invocation")


class FailingMiddleware(RuntimeMiddleware):
    def invoke(self, invocation: RuntimeInvocation, call_next: RuntimeNext) -> Any:
        del invocation, call_next
        raise RuntimeError("middleware failed")


class AsyncRecordingMiddleware(AsyncRuntimeMiddleware):
    def __init__(self, name: str, calls: list[str]) -> None:
        self.name = name
        self.calls = calls

    async def invoke(
        self,
        invocation: RuntimeInvocation,
        call_next: AsyncRuntimeNext,
    ) -> Any:
        self.calls.append(f"{self.name}:before:{invocation.component_name}")
        result = await call_next(invocation)
        self.calls.append(f"{self.name}:after:{invocation.component_name}")
        return result


class AsyncIncrementToolArgumentMiddleware(AsyncRuntimeMiddleware):
    async def invoke(
        self,
        invocation: RuntimeInvocation,
        call_next: AsyncRuntimeNext,
    ) -> Any:
        if isinstance(invocation, ToolInvocation):
            invocation.arguments["right"] += 1
        return await call_next(invocation)


class AsyncShortCircuitAgentMiddleware(AsyncRuntimeMiddleware):
    async def invoke(
        self,
        invocation: RuntimeInvocation,
        call_next: AsyncRuntimeNext,
    ) -> Any:
        del call_next
        if isinstance(invocation, AgentInvocation):
            return Message(role=MessageRole.ASSISTANT, content="from async middleware")
        raise AssertionError("expected an Agent invocation")


class RetryOnceAgent(AsyncAgent):
    def __init__(self) -> None:
        self.attempts = 0

    @property
    def name(self) -> str:
        return "retry_once"

    async def run(self, task: Task, context: Context) -> Message:
        del context
        self.attempts += 1
        if self.attempts == 1:
            raise ConnectionError("retry")
        return Message(role=MessageRole.ASSISTANT, content=task.description)


def test_sync_middleware_wraps_agent_in_registration_order() -> None:
    calls: list[str] = []
    runtime = AgentRuntime(
        middlewares=[
            RecordingMiddleware("outer", calls),
            RecordingMiddleware("inner", calls),
        ]
    )

    result = runtime.run(EchoAgent(), Task(description="hello"))

    assert result.content == "hello"
    assert calls == [
        "outer:before:example_agent",
        "inner:before:example_agent",
        "inner:after:example_agent",
        "outer:after:example_agent",
    ]


def test_sync_middleware_can_change_tool_arguments() -> None:
    runtime = AgentRuntime(middlewares=[IncrementToolArgumentMiddleware()])
    runtime.register_tool(AddTool())

    assert runtime.execute_tool("add", left=2, right=3) == {"result": 6}


def test_sync_middleware_can_short_circuit_and_complete_task() -> None:
    runtime = AgentRuntime(middlewares=[ShortCircuitAgentMiddleware()])
    task = Task(description="ignored")

    result = runtime.run(EchoAgent(), task)

    assert result.content == "from middleware"
    assert task.result is result


def test_sync_middleware_failure_uses_agent_error_semantics() -> None:
    task = Task(description="fail")

    with pytest.raises(AgentExecutionError) as error:
        AgentRuntime(middlewares=[FailingMiddleware()]).run(EchoAgent(), task)

    assert isinstance(error.value.__cause__, RuntimeError)
    assert task.error == "middleware failed"


def test_add_middleware_appends_an_innermost_wrapper() -> None:
    calls: list[str] = []
    outer = RecordingMiddleware("outer", calls)
    inner = RecordingMiddleware("inner", calls)
    runtime = AgentRuntime(middlewares=[outer])

    runtime.add_middleware(inner)
    runtime.run(EchoAgent(), Task(description="hello"))

    assert runtime.middlewares == (outer, inner)
    assert calls[0:2] == ["outer:before:example_agent", "inner:before:example_agent"]


def test_async_middleware_wraps_agent_in_registration_order() -> None:
    async def scenario() -> None:
        calls: list[str] = []
        runtime = AsyncAgentRuntime(
            middlewares=[
                AsyncRecordingMiddleware("outer", calls),
                AsyncRecordingMiddleware("inner", calls),
            ]
        )

        result = await runtime.run(AsyncEchoAgent(), Task(description="hello"))

        assert result.content == "hello"
        assert calls == [
            "outer:before:async_example_agent",
            "inner:before:async_example_agent",
            "inner:after:async_example_agent",
            "outer:after:async_example_agent",
        ]

    asyncio.run(scenario())


def test_async_middleware_can_change_tool_arguments() -> None:
    async def scenario() -> None:
        runtime = AsyncAgentRuntime(middlewares=[AsyncIncrementToolArgumentMiddleware()])
        runtime.register_tool(AsyncAddTool())

        assert await runtime.execute_tool("async_add", left=2, right=3) == {"result": 6}

    asyncio.run(scenario())


def test_async_middleware_can_short_circuit_and_complete_task() -> None:
    async def scenario() -> None:
        runtime = AsyncAgentRuntime(middlewares=[AsyncShortCircuitAgentMiddleware()])
        task = Task(description="ignored")

        result = await runtime.run(AsyncEchoAgent(), task)

        assert result.content == "from async middleware"
        assert task.result is result

    asyncio.run(scenario())


def test_async_middleware_wraps_all_resilience_attempts_once() -> None:
    async def scenario() -> None:
        calls: list[str] = []
        agent = RetryOnceAgent()
        runtime = AsyncAgentRuntime(
            middlewares=[AsyncRecordingMiddleware("audit", calls)],
            resilience_policy=ResiliencePolicy(
                retry=RetryPolicy(
                    max_attempts=2,
                    retry_exceptions=(ConnectionError,),
                )
            ),
        )

        result = await runtime.run(agent, Task(description="retried"))

        assert result.content == "retried"
        assert agent.attempts == 2
        assert calls == ["audit:before:retry_once", "audit:after:retry_once"]

    asyncio.run(scenario())
