"""In-process memory adapter for development and tests."""

from typing import Any

from numa.memory.base import Memory

_MISSING = object()


class InMemoryMemory(Memory):
    """Store values in process without persistence."""

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        return self._values.get(key)

    def set(self, key: str, value: Any) -> None:
        self._values[key] = value

    def delete(self, key: str) -> bool:
        return self._values.pop(key, _MISSING) is not _MISSING

    def clear(self) -> None:
        self._values.clear()
