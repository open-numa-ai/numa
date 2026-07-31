"""Asynchronous Agent Runtime for concurrent task orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar
from uuid import uuid4

from pydantic import ValidationError

from numa.agents import AsyncAgent
from numa.core import (
    AgentExecutionError,
    AgentTimeoutError,
    Context,
    Message,
    Task,
    TaskStatus,
    ToolExecutionError,
    ToolNotFoundError,
    ToolTimeoutError,
    ToolValidationError,
)
from numa.events import Event, EventBus, EventType
from numa.memory import InMemoryMemory, Memory
from numa.runtime.policies import ResiliencePolicy
from numa.runtime.task_persistence import load_task_for_resume, persist_task
from numa.tasks import TaskStore
from numa.tools import AsyncTool
from numa.utils.logging import get_logger

logger = get_logger(__name__)

ResultT = TypeVar("ResultT")


class _ExecutionTimeoutError(Exception):
    """Signal that the Runtime policy deadline expired."""


class AsyncAgentRuntime:
    """Coordinate asynchronous Agents, Tools, memory, and lifecycle events."""

    def __init__(
        self,
        memory: Memory | None = None,
        event_bus: EventBus | None = None,
        resilience_policy: ResiliencePolicy | None = None,
        task_store: TaskStore | None = None,
    ) -> None:
        self.memory = memory or InMemoryMemory()
        self.event_bus = event_bus or EventBus()
        self.resilience_policy = resilience_policy or ResiliencePolicy()
        self.task_store = task_store
        self._tools: dict[str, AsyncTool] = {}

    def register_tool(self, tool: AsyncTool) -> None:
        """Register or replace an asynchronous Tool by its stable name."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> AsyncTool | None:
        """Return a registered asynchronous Tool by name."""
        return self._tools.get(name)

    async def execute_tool(self, name: str, **arguments: Any) -> Any:
        """Validate and execute a Tool with the Runtime's default policy."""
        return await self.execute_tool_with_policy(
            name,
            self.resilience_policy,
            **arguments,
        )

    async def execute_tool_with_policy(
        self,
        name: str,
        resilience_policy: ResiliencePolicy,
        **arguments: Any,
    ) -> Any:
        """Validate and execute a Tool with a per-call resilience policy."""
        execution_id = str(uuid4())
        self.event_bus.emit(
            Event(
                type=EventType.TOOL_STARTED,
                execution_id=execution_id,
                component_name=name,
            )
        )
        try:
            tool = self.get_tool(name)
            if tool is None:
                raise ToolNotFoundError(f"Tool {name!r} is not registered")

            try:
                validated_input = tool.input_model.model_validate(arguments)
            except ValidationError as exc:
                raise ToolValidationError(f"Invalid input for tool {name!r}") from exc

            logger.info("Async Tool execution started", extra={"tool": name})
            try:
                result = await self._execute_with_policy(
                    lambda: tool.execute(**validated_input.model_dump()),
                    resilience_policy,
                    component_name=name,
                )
            except asyncio.CancelledError:
                logger.info("Async Tool execution cancelled", extra={"tool": name})
                self.event_bus.emit(
                    Event(
                        type=EventType.TOOL_CANCELLED,
                        execution_id=execution_id,
                        component_name=name,
                    )
                )
                raise
            except _ExecutionTimeoutError as exc:
                timeout_error = ToolTimeoutError(f"Tool {name!r} execution timed out")
                logger.warning("Async Tool execution timed out", extra={"tool": name})
                raise timeout_error from exc
            except Exception as exc:
                logger.exception("Async Tool execution failed", extra={"tool": name})
                raise ToolExecutionError(f"Tool {name!r} execution failed") from exc

            output_model = tool.output_model
            if output_model is not None:
                try:
                    result = output_model.model_validate(result).model_dump()
                except ValidationError as exc:
                    raise ToolValidationError(f"Invalid output from tool {name!r}") from exc
        except Exception as exc:
            self.event_bus.emit(
                Event(
                    type=EventType.TOOL_FAILED,
                    execution_id=execution_id,
                    component_name=name,
                    metadata={"error_type": type(exc).__name__},
                )
            )
            raise

        logger.info("Async Tool execution completed", extra={"tool": name})
        self.event_bus.emit(
            Event(
                type=EventType.TOOL_COMPLETED,
                execution_id=execution_id,
                component_name=name,
            )
        )
        return result

    async def run(
        self,
        agent: AsyncAgent,
        task: Task,
        context: Context | None = None,
        resilience_policy: ResiliencePolicy | None = None,
    ) -> Message:
        """Run one asynchronous Agent task and update its lifecycle state."""
        execution_context = context or Context()
        task.status = TaskStatus.RUNNING
        task.result = None
        task.error = None
        persist_task(self.task_store, agent.name, task, execution_context)
        self.event_bus.emit(
            Event(
                type=EventType.AGENT_STARTED,
                execution_id=task.id,
                component_name=agent.name,
            )
        )
        logger.info("Async Agent task started", extra={"agent": agent.name, "task_id": task.id})

        try:
            result = await self._execute_with_policy(
                lambda: agent.run(task, execution_context),
                resilience_policy or self.resilience_policy,
                component_name=agent.name,
            )
        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            task.error = "Agent execution cancelled"
            try:
                persist_task(self.task_store, agent.name, task, execution_context)
            except Exception:
                logger.exception(
                    "Could not persist cancelled Agent task",
                    extra={"agent": agent.name, "task_id": task.id},
                )
            logger.info(
                "Async Agent task cancelled",
                extra={"agent": agent.name, "task_id": task.id},
            )
            self.event_bus.emit(
                Event(
                    type=EventType.AGENT_CANCELLED,
                    execution_id=task.id,
                    component_name=agent.name,
                )
            )
            raise
        except _ExecutionTimeoutError as exc:
            timeout_error = AgentTimeoutError(f"Agent {agent.name!r} timed out task {task.id}")
            task.status = TaskStatus.FAILED
            task.error = str(timeout_error)
            persist_task(self.task_store, agent.name, task, execution_context)
            logger.warning(
                "Async Agent task timed out",
                extra={"agent": agent.name, "task_id": task.id},
            )
            self.event_bus.emit(
                Event(
                    type=EventType.AGENT_FAILED,
                    execution_id=task.id,
                    component_name=agent.name,
                    metadata={"error_type": type(timeout_error).__name__},
                )
            )
            raise timeout_error from exc
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            persist_task(self.task_store, agent.name, task, execution_context)
            logger.exception(
                "Async Agent task failed",
                extra={"agent": agent.name, "task_id": task.id},
            )
            self.event_bus.emit(
                Event(
                    type=EventType.AGENT_FAILED,
                    execution_id=task.id,
                    component_name=agent.name,
                    metadata={"error_type": type(exc).__name__},
                )
            )
            raise AgentExecutionError(f"Agent {agent.name!r} failed task {task.id}") from exc

        execution_context.add_message(result)
        task.result = result
        task.status = TaskStatus.COMPLETED
        persist_task(self.task_store, agent.name, task, execution_context)
        logger.info(
            "Async Agent task completed",
            extra={"agent": agent.name, "task_id": task.id},
        )
        self.event_bus.emit(
            Event(
                type=EventType.AGENT_COMPLETED,
                execution_id=task.id,
                component_name=agent.name,
            )
        )
        return result

    async def resume(
        self,
        agent: AsyncAgent,
        task_id: str,
        resilience_policy: ResiliencePolicy | None = None,
    ) -> Message:
        """Return a completed result or rerun a persisted unfinished Task."""
        record = load_task_for_resume(self.task_store, task_id, agent.name)
        if record.task.status is TaskStatus.COMPLETED:
            assert record.task.result is not None
            return record.task.result
        return await self.run(
            agent,
            record.task,
            record.context,
            resilience_policy=resilience_policy,
        )

    async def gather(
        self,
        *runs: tuple[AsyncAgent, Task],
        resilience_policy: ResiliencePolicy | None = None,
    ) -> list[Message]:
        """Run multiple Agent tasks concurrently and preserve input order."""
        return list(
            await asyncio.gather(
                *(
                    self.run(agent, task, resilience_policy=resilience_policy)
                    for agent, task in runs
                )
            )
        )

    async def _execute_with_policy(
        self,
        operation: Callable[[], Awaitable[ResultT]],
        policy: ResiliencePolicy,
        *,
        component_name: str,
    ) -> ResultT:
        timeout = asyncio.timeout(policy.timeout_seconds)
        try:
            async with timeout:
                attempt = 1
                while True:
                    try:
                        return await operation()
                    except Exception as exc:
                        if not policy.retry.should_retry(exc, attempt):
                            raise
                        attempt += 1
                        delay = policy.retry.delay_before_attempt(attempt)
                        logger.warning(
                            "Async execution retry scheduled",
                            extra={
                                "component": component_name,
                                "attempt": attempt,
                                "delay_seconds": delay,
                                "error_type": type(exc).__name__,
                            },
                        )
                        await asyncio.sleep(delay)
        except TimeoutError as exc:
            if timeout.expired():
                raise _ExecutionTimeoutError from exc
            raise
