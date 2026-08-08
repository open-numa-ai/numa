"""Tool permission policies enforced by Runtime execution boundaries."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from numa.core import ToolPermissionDeniedError, ToolPermissionPolicyError


@dataclass(frozen=True, slots=True)
class ToolPermissionRequest:
    """Describe a normalized Tool call presented to a permission policy."""

    execution_id: str
    tool_name: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ToolPermissionDecision:
    """Represent one explicit allow or deny policy result."""

    allowed: bool
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.allowed, bool):
            raise ValueError("allowed must be a bool")
        if self.reason is not None and not isinstance(self.reason, str):
            raise ValueError("reason must be a string or None")

    @classmethod
    def allow(cls) -> ToolPermissionDecision:
        """Create an allow decision."""
        return cls(allowed=True)

    @classmethod
    def deny(cls, reason: str | None = None) -> ToolPermissionDecision:
        """Create a deny decision with an optional safe explanation."""
        return cls(allowed=False, reason=reason)


class ToolPermissionPolicy(ABC):
    """Decide whether a normalized Tool invocation may proceed."""

    @abstractmethod
    def evaluate(self, request: ToolPermissionRequest) -> ToolPermissionDecision:
        """Return an explicit permission decision without performing I/O."""


class AllowAllToolPolicy(ToolPermissionPolicy):
    """Allow every registered Tool. This preserves Runtime defaults."""

    def evaluate(self, request: ToolPermissionRequest) -> ToolPermissionDecision:
        del request
        return ToolPermissionDecision.allow()


class DenyAllToolPolicy(ToolPermissionPolicy):
    """Deny every Tool invocation."""

    def evaluate(self, request: ToolPermissionRequest) -> ToolPermissionDecision:
        del request
        return ToolPermissionDecision.deny("all Tool execution is disabled")


@dataclass(frozen=True, slots=True, init=False)
class ToolAllowlistPolicy(ToolPermissionPolicy):
    """Allow only Tool names explicitly included in an immutable allowlist."""

    allowed_tools: frozenset[str]

    def __init__(self, allowed_tools: Iterable[str]) -> None:
        object.__setattr__(self, "allowed_tools", _normalize_tool_names(allowed_tools))

    def evaluate(self, request: ToolPermissionRequest) -> ToolPermissionDecision:
        if request.tool_name in self.allowed_tools:
            return ToolPermissionDecision.allow()
        return ToolPermissionDecision.deny("Tool is not in the configured allowlist")


@dataclass(frozen=True, slots=True, init=False)
class ToolDenylistPolicy(ToolPermissionPolicy):
    """Deny Tool names explicitly included in an immutable denylist."""

    denied_tools: frozenset[str]

    def __init__(self, denied_tools: Iterable[str]) -> None:
        object.__setattr__(self, "denied_tools", _normalize_tool_names(denied_tools))

    def evaluate(self, request: ToolPermissionRequest) -> ToolPermissionDecision:
        if request.tool_name in self.denied_tools:
            return ToolPermissionDecision.deny("Tool is in the configured denylist")
        return ToolPermissionDecision.allow()


def enforce_tool_permission(
    policy: ToolPermissionPolicy,
    *,
    execution_id: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> None:
    """Evaluate a policy and raise a stable framework error unless it allows execution."""
    request = ToolPermissionRequest(
        execution_id=execution_id,
        tool_name=tool_name,
        arguments=MappingProxyType(arguments),
    )
    try:
        decision = policy.evaluate(request)
    except Exception as exc:
        raise ToolPermissionPolicyError(
            f"Permission policy failed while evaluating Tool {tool_name!r}"
        ) from exc

    if not isinstance(decision, ToolPermissionDecision):
        raise ToolPermissionPolicyError(
            f"Permission policy returned an invalid decision for Tool {tool_name!r}"
        )
    if decision.allowed:
        return

    message = f"Permission denied for Tool {tool_name!r}"
    if decision.reason:
        message = f"{message}: {decision.reason}"
    raise ToolPermissionDeniedError(message)


def _normalize_tool_names(tool_names: Iterable[str]) -> frozenset[str]:
    if isinstance(tool_names, str):
        raise ValueError("Tool names must be provided as an iterable of non-empty strings")
    names = tuple(tool_names)
    if any(not isinstance(name, str) or not name for name in names):
        raise ValueError("Tool names must be non-empty strings")
    return frozenset(names)
