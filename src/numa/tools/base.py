"""Tool extension point."""

from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    """A capability that can be registered with an agent runtime."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique tool name used for lookup."""

    @property
    def description(self) -> str:
        """Return a human-readable description of the tool."""
        return ""

    @abstractmethod
    def execute(self, **arguments: Any) -> Any:
        """Execute the tool with validated implementation-specific arguments."""
