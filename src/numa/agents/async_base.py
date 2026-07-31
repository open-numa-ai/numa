"""Asynchronous Agent extension point."""

from abc import ABC, abstractmethod

from numa.core import Context, Message, Task


class AsyncAgent(ABC):
    """Base abstraction for an asynchronously executed Agent."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the stable name used to identify this Agent."""

    @abstractmethod
    async def run(self, task: Task, context: Context) -> Message:
        """Execute a task asynchronously and return the Agent response."""