"""Asynchronous Tool extension point."""

from abc import abstractmethod
from typing import Any

from numa.tools.base import ToolSchema


class AsyncTool(ToolSchema):
    """A capability that can be registered with an asynchronous Runtime."""

    @abstractmethod
    async def execute(self, **arguments: Any) -> Any:
        """Execute the Tool asynchronously with validated arguments."""