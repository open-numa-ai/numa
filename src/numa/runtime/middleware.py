"""Composable middleware contracts for Runtime component execution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, TypeAlias

from numa.core import Context, Task


@dataclass(frozen=True, slots=True)
class AgentInvocation:
    """Describe one Agent call as it passes through middleware."""

    execution_id: str
    component_name: str
    task: Task
    context: Context
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolInvocation:
    """Describe one Tool call with normalized, mutable arguments."""

    execution_id: str
    component_name: str
    arguments: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


RuntimeInvocation: TypeAlias = AgentInvocation | ToolInvocation
RuntimeNext: TypeAlias = Callable[[RuntimeInvocation], Any]
AsyncRuntimeNext: TypeAlias = Callable[[RuntimeInvocation], Awaitable[Any]]


class RuntimeMiddleware(ABC):
    """Wrap synchronous Agent and Tool component calls."""

    @abstractmethod
    def invoke(
        self,
        invocation: RuntimeInvocation,
        call_next: RuntimeNext,
    ) -> Any:
        """Inspect, alter, short-circuit, or continue an invocation."""


class AsyncRuntimeMiddleware(ABC):
    """Wrap asynchronous Agent and Tool component calls."""

    @abstractmethod
    async def invoke(
        self,
        invocation: RuntimeInvocation,
        call_next: AsyncRuntimeNext,
    ) -> Any:
        """Inspect, alter, short-circuit, or await the next invocation."""


def compose_middleware(
    middlewares: Iterable[RuntimeMiddleware],
    terminal: RuntimeNext,
) -> RuntimeNext:
    """Compose synchronous middleware with the first item outermost."""
    handler = terminal
    for middleware in reversed(tuple(middlewares)):
        handler = _wrap_middleware(middleware, handler)
    return handler


def compose_async_middleware(
    middlewares: Iterable[AsyncRuntimeMiddleware],
    terminal: AsyncRuntimeNext,
) -> AsyncRuntimeNext:
    """Compose asynchronous middleware with the first item outermost."""
    handler = terminal
    for middleware in reversed(tuple(middlewares)):
        handler = _wrap_async_middleware(middleware, handler)
    return handler


def _wrap_middleware(
    middleware: RuntimeMiddleware,
    call_next: RuntimeNext,
) -> RuntimeNext:
    def invoke(invocation: RuntimeInvocation) -> Any:
        return middleware.invoke(invocation, call_next)

    return invoke


def _wrap_async_middleware(
    middleware: AsyncRuntimeMiddleware,
    call_next: AsyncRuntimeNext,
) -> AsyncRuntimeNext:
    async def invoke(invocation: RuntimeInvocation) -> Any:
        return await middleware.invoke(invocation, call_next)

    return invoke
