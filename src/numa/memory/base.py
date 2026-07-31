"""Memory extension point."""

from abc import ABC, abstractmethod
from typing import Any


class Memory(ABC):
    """Key-value memory interface used by agents and runtimes."""

    @abstractmethod
    def get(self, key: str) -> Any | None:
        """Return a stored value, or None when the key is absent."""

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Store a value under a key."""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a key and report whether it existed."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all stored values."""
