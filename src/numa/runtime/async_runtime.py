"""Asynchronous Agent Runtime for concurrent task orchestration."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from numa.agents import AsyncAgent
from numa.core import (
    AgentExecutionError,
    Context,
    Message,
    Task,
    TaskStatus,
    ToolExecutionError,
    ToolNotFoundError,
    ToolValidationError,
)
from numa.events import Event, EventBus, EventType
from numa.memory import InMemoryMemory, Memory
from numa.tools import AsyncTool
from numa.utils.logging import get_logger

logger = get_logger(__name__)


class AsyncAgentRuntime:
    """Coordinate asynchronous Agents, Tools, memory, and lifecycle events."""

    def __init__(self, memory: Memory | None = None, event_bus: EventBus | None = None) -> None:
        self.memory = memory or InMemoryMemory()
        self.event_bus = event_bus or EventBus()
        self._tools: dict[str, AsyncTool] = {}

    def register_tool(self, tool: AsyncTool) -> None:
        """Register or replace an asynchronous Tool by its stable name."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> AsyncTool | None:
        """Return a registered asynchronous Tool by name."""
        return self._tools.get(name)

    async def execute_tool(self, name: str, **arguments: Any) -> Any:
        """Validate and execute a registered asynchronous Tool."""
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
                result = await tool.execute(**validated_input.model_dump())
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
    ) -> Message:
        """Run one asynchronous Agent task and update its lifecycle state."""
        execution_context = context or Context()
        task.status = TaskStatus.RUNNING
        self.event_bus.emit(
            Event(
                type=EventType.AGENT_STARTED,
                execution_id=task.id,
                component_name=agent.name,
            )
        )
        logger.info("Async Agent task started", extra={"agent": agent.name, "task_id": task.id})

        try:
            result = await agent.run(task, execution_context)
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
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

    async def gather(self, *runs: tuple[AsyncAgent, Task]) -> list[Message]:
        """Run multiple Agent tasks concurrently and preserve input order."""
        return list(await asyncio.gather(*(self.run(agent, task) for agent, task in runs)))