from __future__ import annotations

import asyncio
from typing import Any

import pytest

from numa import (
    AgentRuntime,
    AsyncAgentRuntime,
    DenyAllToolPolicy,
    ResiliencePolicy,
    RetryPolicy,
    RuntimeInvocation,
    RuntimeMiddleware,
    RuntimeNext,
    ToolAllowlistPolicy,
    ToolDenylistPolicy,
    ToolInvocation,
    ToolPermissionDecision,
    ToolPermissionDeniedError,
    ToolPermissionPolicy,
    ToolPermissionPolicyError,
    ToolPermissionRequest,
)
from numa.events import EventBus, EventType, InMemoryEventHandler
from numa.tools import AddTool, AsyncAddTool


class ArgumentPolicy(ToolPermissionPolicy):
    def evaluate(self, request: ToolPermissionRequest) -> ToolPermissionDecision:
        if request.arguments["left"] <= 5:
            return ToolPermissionDecision.allow()
        return ToolPermissionDecision.deny("left exceeds the configured limit")


class BrokenPolicy(ToolPermissionPolicy):
    def evaluate(self, request: ToolPermissionRequest) -> ToolPermissionDecision:
        del request
        raise RuntimeError("policy backend unavailable")


class InvalidDecisionPolicy(ToolPermissionPolicy):
    def evaluate(self, request: ToolPermissionRequest) -> ToolPermissionDecision:
        del request
        return True  # type: ignore[return-value]


class RecordingMiddleware(RuntimeMiddleware):
    def __init__(self) -> None:
        self.called = False

    def invoke(self, invocation: RuntimeInvocation, call_next: RuntimeNext) -> Any:
        assert isinstance(invocation, ToolInvocation)
        self.called = True
        return call_next(invocation)


def test_default_policy_preserves_tool_execution() -> None:
    runtime = AgentRuntime()
    runtime.register_tool(AddTool())

    assert runtime.execute_tool("add", left=2, right=3) == {"result": 5}


def test_allowlist_allows_only_named_tools() -> None:
    policy = ToolAllowlistPolicy(["add"])
    runtime = AgentRuntime(tool_permission_policy=policy)
    runtime.register_tool(AddTool())

    assert policy.allowed_tools == frozenset({"add"})
    assert runtime.execute_tool("add", left=2, right=3) == {"result": 5}

    denied_runtime = AgentRuntime(tool_permission_policy=ToolAllowlistPolicy([]))
    denied_runtime.register_tool(AddTool())
    with pytest.raises(ToolPermissionDeniedError, match="allowlist"):
        denied_runtime.execute_tool("add", left=2, right=3)


def test_denylist_denies_only_named_tools() -> None:
    policy = ToolDenylistPolicy(["dangerous"])
    runtime = AgentRuntime(tool_permission_policy=policy)
    runtime.register_tool(AddTool())

    assert policy.denied_tools == frozenset({"dangerous"})
    assert runtime.execute_tool("add", left=2, right=3) == {"result": 5}

    denied_runtime = AgentRuntime(tool_permission_policy=ToolDenylistPolicy(["add"]))
    denied_runtime.register_tool(AddTool())
    with pytest.raises(ToolPermissionDeniedError, match="denylist"):
        denied_runtime.execute_tool("add", left=2, right=3)


def test_custom_policy_receives_normalized_arguments() -> None:
    runtime = AgentRuntime(tool_permission_policy=ArgumentPolicy())
    runtime.register_tool(AddTool())

    assert runtime.execute_tool("add", left=5, right=1) == {"result": 6}
    with pytest.raises(ToolPermissionDeniedError, match="configured limit"):
        runtime.execute_tool("add", left=6, right=1)


def test_denied_tool_does_not_enter_middleware() -> None:
    middleware = RecordingMiddleware()
    runtime = AgentRuntime(
        middlewares=[middleware],
        tool_permission_policy=DenyAllToolPolicy(),
    )
    runtime.register_tool(AddTool())

    with pytest.raises(ToolPermissionDeniedError):
        runtime.execute_tool("add", left=2, right=3)

    assert middleware.called is False


@pytest.mark.parametrize("policy", [BrokenPolicy(), InvalidDecisionPolicy()])
def test_policy_errors_fail_closed(policy: ToolPermissionPolicy) -> None:
    runtime = AgentRuntime(tool_permission_policy=policy)
    runtime.register_tool(AddTool())

    with pytest.raises(ToolPermissionPolicyError):
        runtime.execute_tool("add", left=2, right=3)


def test_denial_emits_failed_event_without_arguments() -> None:
    collector = InMemoryEventHandler()
    runtime = AgentRuntime(
        event_bus=EventBus([collector]),
        tool_permission_policy=DenyAllToolPolicy(),
    )
    runtime.register_tool(AddTool())

    with pytest.raises(ToolPermissionDeniedError):
        runtime.execute_tool("add", left=2, right=3)

    assert [event.type for event in collector.events] == [
        EventType.TOOL_STARTED,
        EventType.TOOL_FAILED,
    ]
    assert collector.events[-1].metadata == {"error_type": "ToolPermissionDeniedError"}


def test_async_denial_happens_outside_retry_boundary() -> None:
    async def scenario() -> None:
        policy = DenyAllToolPolicy()
        runtime = AsyncAgentRuntime(
            resilience_policy=ResiliencePolicy(
                retry=RetryPolicy(max_attempts=3, retry_exceptions=(Exception,))
            ),
            tool_permission_policy=policy,
        )
        runtime.register_tool(AsyncAddTool())

        with pytest.raises(ToolPermissionDeniedError):
            await runtime.execute_tool("async_add", left=2, right=3)

    asyncio.run(scenario())


@pytest.mark.parametrize("policy_type", [ToolAllowlistPolicy, ToolDenylistPolicy])
def test_name_policies_reject_empty_tool_names(
    policy_type: type[ToolAllowlistPolicy] | type[ToolDenylistPolicy],
) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        policy_type([""])


@pytest.mark.parametrize("policy_type", [ToolAllowlistPolicy, ToolDenylistPolicy])
def test_name_policies_reject_a_bare_string(
    policy_type: type[ToolAllowlistPolicy] | type[ToolDenylistPolicy],
) -> None:
    with pytest.raises(ValueError, match="iterable"):
        policy_type("add")
