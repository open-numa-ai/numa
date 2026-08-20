"""Optional OpenTelemetry adapter for Numa lifecycle span records.

The module uses structural protocols instead of importing OpenTelemetry. This
keeps the tracing SDK outside Numa's dependencies and lets applications inject
an SDK-configured tracer and error status.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Protocol, TypeAlias

from numa import SpanRecord

_ScalarAttribute: TypeAlias = bool | int | float | str
_AttributeValue: TypeAlias = _ScalarAttribute | Sequence[_ScalarAttribute]


class _OpenTelemetrySpan(Protocol):
    def set_status(self, status: Any) -> None:
        """Set the OpenTelemetry span status."""

    def end(self) -> None:
        """End the span."""


class OpenTelemetryTracer(Protocol):
    """Minimal structural boundary implemented by an OpenTelemetry tracer."""

    def start_span(
        self,
        name: str,
        *,
        attributes: Mapping[str, _AttributeValue] | None = None,
    ) -> _OpenTelemetrySpan:
        """Start one span without changing the current context."""


@dataclass(frozen=True, slots=True)
class OpenTelemetrySpanExporter:
    """Export each Numa lifecycle transition as a short OpenTelemetry span.

    The exporter deliberately does not reconstruct long-running parent/child
    spans from separate lifecycle events. Any active application context may
    still become the parent according to the injected tracer's normal rules.
    """

    tracer: OpenTelemetryTracer
    error_status: Any

    def export(self, record: SpanRecord) -> None:
        span = self.tracer.start_span(record.name, attributes=_attributes(record))
        try:
            if record.status == "failed":
                span.set_status(self.error_status)
        finally:
            span.end()


def create_opentelemetry_exporter(
    instrumentation_name: str = "numa",
    *,
    tracer_provider: Any | None = None,
) -> OpenTelemetrySpanExporter:
    """Create an exporter from an installed OpenTelemetry API package."""
    if not instrumentation_name.strip():
        raise ValueError("instrumentation_name cannot be empty")

    try:
        trace = import_module("opentelemetry.trace")
    except ImportError as exc:
        raise RuntimeError(
            "Install the optional OpenTelemetry SDK with `uv run --with opentelemetry-sdk ...`"
        ) from exc

    tracer = trace.get_tracer(instrumentation_name, tracer_provider=tracer_provider)
    error_status = trace.Status(trace.StatusCode.ERROR)
    return OpenTelemetrySpanExporter(tracer=tracer, error_status=error_status)


def _attributes(record: SpanRecord) -> dict[str, _AttributeValue]:
    attributes: dict[str, _AttributeValue] = {
        "numa.execution.id": record.execution_id,
        "numa.component.name": record.component_name,
        "numa.lifecycle.status": record.status,
    }
    for key, value in record.attributes.items():
        normalized = _normalize_attribute(value)
        if normalized is None:
            continue
        attribute_name = (
            "numa.component.type" if key == "component_type" else f"numa.metadata.{key}"
        )
        attributes[attribute_name] = normalized
    return attributes


def _normalize_attribute(value: Any) -> _AttributeValue | None:
    if isinstance(value, (bool, int, float, str)):
        return value
    if not isinstance(value, (list, tuple)) or not value:
        return None
    first_type = type(value[0])
    if first_type not in {bool, int, float, str}:
        return None
    if not all(type(item) is first_type for item in value):
        return None
    return tuple(value)
