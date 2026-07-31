"""Synchronous agent runtime for task orchestration."""

from numa.agents import Agent
from numa.core import AgentExecutionError, Context, Message, Task, TaskStatus
from numa.memory import InMemoryMemory, Memory
from numa.tools import Tool
from numa.utils.logging import get_logger

logger = get_logger(__name__)


class AgentRuntime:
    """Coordinate an agent, task lifecycle, tools, and memory."""

    def __init__(self, memory: Memory | None = None) -> None:
        self.memory = memory or InMemoryMemory()
        self._tools: dict[str, Tool] = {}

    def register_tool(self, tool: Tool) -> None:
        """Register or replace a tool by its stable name."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Tool | None:
        """Return a registered tool by name."""
        return self._tools.get(name)

    def run(self, agent: Agent, task: Task, context: Context | None = None) -> Message:
        """Run one agent task and update its lifecycle state."""
        execution_context = context or Context()
        task.status = TaskStatus.RUNNING
        logger.info("Agent task started", extra={"agent": agent.name, "task_id": task.id})

        try:
            result = agent.run(task, execution_context)
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            logger.exception("Agent task failed", extra={"agent": agent.name, "task_id": task.id})
            raise AgentExecutionError(f"Agent {agent.name!r} failed task {task.id}") from exc

        execution_context.add_message(result)
        task.result = result
        task.status = TaskStatus.COMPLETED
        logger.info("Agent task completed", extra={"agent": agent.name, "task_id": task.id})
        return result
