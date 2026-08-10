"""Provider-neutral observability bridge for lifecycle events.

The core package intentionally does not depend on OpenTelemetry or another
tracing SDK. Applications can adapt :class:`SpanExporter` to their preferred
backend while retaining Numa's privacy-safe event boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Protocol

from numa.events.handlers import EventHandler
from numa.events.models import Event


@dataclass(frozen=True, slots=True)
class SpanRecord:
    """A backend-neutral representation of one lifecycle span transition."""

    name: str
    execution_id: str
    component_name: str
    status: str
    attributes: dict[str, Any] = field(default_factory=dict)


class SpanExporter(Protocol):
    """Minimal sink implemented by an application or tracing adapter."""

    def export(self, span: SpanRecord) -> None:
        """Export one span transition."""


class EventSpanHandler(EventHandler):
    """Convert Numa lifecycle events into privacy-safe span records.

    Event payloads do not contain prompts, responses, or tool arguments. The
    handler forwards only event metadata, so applications remain responsible
    for any additional redaction policy in their exporter.
    """

    def __init__(self, exporter: SpanExporter) -> None:
        self._exporter = exporter

    def handle(self, event: Event) -> None:
        prefix, _, status = event.type.value.partition(".")
        self._exporter.export(
            SpanRecord(
                name=f"numa.{event.type.value}",
                execution_id=event.execution_id,
                component_name=event.component_name,
                status=status,
                attributes={"component_type": prefix, **event.metadata},
            )
        )


class InMemorySpanExporter:
    """Thread-safe exporter useful for tests and local development."""

    def __init__(self) -> None:
        self._spans: list[SpanRecord] = []
        self._lock = RLock()

    @property
    def spans(self) -> tuple[SpanRecord, ...]:
        """Return an immutable snapshot of exported spans."""
        with self._lock:
            return tuple(self._spans)

    def export(self, span: SpanRecord) -> None:
        with self._lock:
            self._spans.append(span)
