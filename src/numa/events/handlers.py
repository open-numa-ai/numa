"""Event handler contracts and built-in implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from threading import RLock

from numa.events.models import Event


class EventHandler(ABC):
    """Receive structured events from an EventBus."""

    @abstractmethod
    def handle(self, event: Event) -> None:
        """Handle one event."""


class NoOpEventHandler(EventHandler):
    """Discard events without side effects."""

    def handle(self, event: Event) -> None:
        del event


class InMemoryEventHandler(EventHandler):
    """Collect events in memory for tests and local inspection."""

    def __init__(self) -> None:
        self._events: list[Event] = []
        self._lock = RLock()

    @property
    def events(self) -> tuple[Event, ...]:
        """Return an immutable snapshot of collected events."""
        with self._lock:
            return tuple(self._events)

    def handle(self, event: Event) -> None:
        with self._lock:
            self._events.append(event)

    def clear(self) -> None:
        """Remove all collected events."""
        with self._lock:
            self._events.clear()
