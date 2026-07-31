"""Agent extension point."""

from abc import ABC, abstractmethod

from numa.core import Context, Message, Task


class Agent(ABC):
    """Base abstraction for an AI agent."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the stable name used to identify this agent."""

    @abstractmethod
    def run(self, task: Task, context: Context) -> Message:
        """Execute a task and return the agent's response."""
