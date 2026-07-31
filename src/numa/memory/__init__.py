"""Memory abstractions and built-in adapters."""

from numa.memory.base import Memory
from numa.memory.in_memory import InMemoryMemory

__all__ = ["InMemoryMemory", "Memory"]
