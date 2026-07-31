"""Failure-isolated dispatch for structured events."""

from __future__ import annotations

from collections.abc import Iterable
from threading import RLock

from numa.events.handlers import EventHandler
from numa.events.models import Event
from numa.utils.logging import get_logger

logger = get_logger(__name__)


class EventBus:
    """Dispatch events to handlers without disrupting framework execution."""

    def __init__(self, handlers: Iterable[EventHandler] = ()) -> None:
        self._handlers = list(handlers)
        self._lock = RLock()

    def add_handler(self, handler: EventHandler) -> None:
        """Register a handler for future events."""
        with self._lock:
            self._handlers.append(handler)

    def emit(self, event: Event) -> None:
        """Dispatch an event and isolate failures from each handler."""
        with self._lock:
            handlers = tuple(self._handlers)

        for handler in handlers:
            try:
                handler.handle(event)
            except Exception:
                logger.exception(
                    "Event handler failed",
                    extra={"event_id": event.id, "event_type": event.type.value},
                )