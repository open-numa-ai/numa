"""Synchronous agent runtime for task orchestration."""

from collections.abc import Iterable
from typing import Any, cast
from uuid import uuid4

from pydantic import ValidationError

from numa.agents import Agent
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
from numa.runtime.middleware import (
    AgentInvocation,
    RuntimeInvocation,
    RuntimeMiddleware,
    ToolInvocation,
    compose_middleware,
)
from numa.runtime.task_persistence import load_task_for_resume, persist_task
from numa.tasks import TaskStore
from numa.tools import Tool
from numa.utils.logging import get_logger

logger = get_logger(__name__)


class AgentRuntime:
    """Coordinate an agent, task lifecycle, tools, and memory."""

    def __init__(
        self,
        memory: Memory | None = None,
        event_bus: EventBus | None = None,
        task_store: TaskStore | None = None,
        middlewares: Iterable[RuntimeMiddleware] = (),
    ) -> None:
        self.memory = memory or InMemoryMemory()
        self.event_bus = event_bus or EventBus()
        self.task_store = task_store
        self._middlewares = tuple(middlewares)
        self._tools: dict[str, Tool] = {}

    @property
    def middlewares(self) -> tuple[RuntimeMiddleware, ...]:
        """Return middleware in outermost-to-innermost execution order."""
        return self._middlewares

    def add_middleware(self, middleware: RuntimeMiddleware) -> None:
        """Append middleware as the innermost wrapper for future calls."""
        self._middlewares += (middleware,)

    def register_tool(self, tool: Tool) -> None:
        """Register or replace a tool by its stable name."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Tool | None:
        """Return a registered tool by name."""
        return self._tools.get(name)

    def execute_tool(self, name: str, **arguments: Any) -> Any:
        """Validate and execute a registered tool by name."""
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

            logger.info("Tool execution started", extra={"tool": name})
            try:
                invocation = ToolInvocation(
                    execution_id=execution_id,
                    component_name=name,
                    arguments=validated_input.model_dump(),
                )

                def execute(invocation: RuntimeInvocation) -> Any:
                    if not isinstance(invocation, ToolInvocation):
                        raise TypeError("Tool middleware must forward a ToolInvocation")
                    return tool.execute(**invocation.arguments)

                result = compose_middleware(self._middlewares, execute)(invocation)
            except Exception as exc:
                logger.exception("Tool execution failed", extra={"tool": name})
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

        logger.info("Tool execution completed", extra={"tool": name})
        self.event_bus.emit(
            Event(
                type=EventType.TOOL_COMPLETED,
                execution_id=execution_id,
                component_name=name,
            )
        )
        return result

    def run(self, agent: Agent, task: Task, context: Context | None = None) -> Message:
        """Run one agent task and update its lifecycle state."""
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
        logger.info("Agent task started", extra={"agent": agent.name, "task_id": task.id})

        try:
            invocation = AgentInvocation(
                execution_id=task.id,
                component_name=agent.name,
                task=task,
                context=execution_context,
            )

            def execute(invocation: RuntimeInvocation) -> Message:
                if not isinstance(invocation, AgentInvocation):
                    raise TypeError("Agent middleware must forward an AgentInvocation")
                return agent.run(invocation.task, invocation.context)

            result = cast(Message, compose_middleware(self._middlewares, execute)(invocation))
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            persist_task(self.task_store, agent.name, task, execution_context)
            logger.exception("Agent task failed", extra={"agent": agent.name, "task_id": task.id})
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
        logger.info("Agent task completed", extra={"agent": agent.name, "task_id": task.id})
        self.event_bus.emit(
            Event(
                type=EventType.AGENT_COMPLETED,
                execution_id=task.id,
                component_name=agent.name,
            )
        )
        return result

    def resume(self, agent: Agent, task_id: str) -> Message:
        """Return a completed result or rerun a persisted unfinished Task."""
        record = load_task_for_resume(self.task_store, task_id, agent.name)
        if record.task.status is TaskStatus.COMPLETED:
            assert record.task.result is not None
            return record.task.result
        return self.run(agent, record.task, record.context)
