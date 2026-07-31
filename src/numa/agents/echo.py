"""Minimal agent used for examples and smoke tests."""

from numa.agents.base import Agent
from numa.core import Context, Message, MessageRole, Task


class EchoAgent(Agent):
    """Return the submitted task description without model inference."""

    @property
    def name(self) -> str:
        return "example_agent"

    def run(self, task: Task, context: Context) -> Message:
        del context
        return Message(role=MessageRole.ASSISTANT, content=task.description)
