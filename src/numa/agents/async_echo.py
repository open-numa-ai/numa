"""Deterministic asynchronous Agent implementation."""

from numa.agents.async_base import AsyncAgent
from numa.core import Context, Message, MessageRole, Task


class AsyncEchoAgent(AsyncAgent):
    """Return the task description as an asynchronous Agent response."""

    @property
    def name(self) -> str:
        return "async_example_agent"

    async def run(self, task: Task, context: Context) -> Message:
        del context
        return Message(role=MessageRole.ASSISTANT, content=task.description)
