from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from numa import AgentRuntime, EventBus, EventSpanHandler, SpanRecord, Task
from numa.agents import EchoAgent

_MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "examples" / "adapters" / "opentelemetry_spans.py"
)
_SPEC = importlib.util.spec_from_file_location("numa_opentelemetry_span_adapter", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)

OpenTelemetrySpanExporter = _MODULE.OpenTelemetrySpanExporter
create_opentelemetry_exporter = _MODULE.create_opentelemetry_exporter


class RecordingSpan:
    def __init__(self, name: str, attributes: dict[str, Any]) -> None:
        self.name = name
        self.attributes = attributes
        self.statuses: list[Any] = []
        self.ended = False

    def set_status(self, status: Any) -> None:
        self.statuses.append(status)

    def end(self) -> None:
        self.ended = True


class RecordingTracer:
    def __init__(self) -> None:
        self.spans: list[RecordingSpan] = []

    def start_span(
        self,
        name: str,
        *,
        attributes: dict[str, Any] | None = None,
    ) -> RecordingSpan:
        span = RecordingSpan(name, dict(attributes or {}))
        self.spans.append(span)
        return span


class FailingStatusSpan(RecordingSpan):
    def set_status(self, status: Any) -> None:
        del status
        raise RuntimeError("status unavailable")


class FailingStatusTracer(RecordingTracer):
    def start_span(
        self,
        name: str,
        *,
        attributes: dict[str, Any] | None = None,
    ) -> RecordingSpan:
        span = FailingStatusSpan(name, dict(attributes or {}))
        self.spans.append(span)
        return span


def test_adapter_maps_lifecycle_record_to_opentelemetry_span() -> None:
    tracer = RecordingTracer()
    exporter = OpenTelemetrySpanExporter(tracer, error_status="ERROR")

    exporter.export(
        SpanRecord(
            name="numa.agent.completed",
            execution_id="task-123",
            component_name="assistant",
            status="completed",
            attributes={
                "component_type": "agent",
                "model": "fixture-model",
                "attempts": 2,
                "cached": False,
                "tags": ["offline", "test"],
            },
        )
    )

    span = tracer.spans[0]
    assert span.name == "numa.agent.completed"
    assert span.attributes == {
        "numa.execution.id": "task-123",
        "numa.component.name": "assistant",
        "numa.component.type": "agent",
        "numa.lifecycle.status": "completed",
        "numa.metadata.model": "fixture-model",
        "numa.metadata.attempts": 2,
        "numa.metadata.cached": False,
        "numa.metadata.tags": ("offline", "test"),
    }
    assert span.statuses == []
    assert span.ended


def test_adapter_marks_failed_records_as_errors() -> None:
    tracer = RecordingTracer()
    error_status = object()
    exporter = OpenTelemetrySpanExporter(tracer, error_status=error_status)

    exporter.export(
        SpanRecord(
            name="numa.tool.failed",
            execution_id="tool-123",
            component_name="lookup",
            status="failed",
            attributes={"component_type": "tool", "error_type": "ValueError"},
        )
    )

    assert tracer.spans[0].statuses == [error_status]
    assert tracer.spans[0].attributes["numa.metadata.error_type"] == "ValueError"
    assert tracer.spans[0].ended


@pytest.mark.parametrize("status", ["started", "completed", "cancelled"])
def test_adapter_leaves_non_failure_status_unset(status: str) -> None:
    tracer = RecordingTracer()
    exporter = OpenTelemetrySpanExporter(tracer, error_status="ERROR")

    exporter.export(SpanRecord("numa.agent.event", "task", "agent", status))

    assert tracer.spans[0].statuses == []
    assert tracer.spans[0].ended


def test_adapter_drops_unsupported_attribute_values() -> None:
    tracer = RecordingTracer()
    exporter = OpenTelemetrySpanExporter(tracer, error_status="ERROR")

    exporter.export(
        SpanRecord(
            "numa.agent.completed",
            "task",
            "agent",
            "completed",
            attributes={
                "component_type": "agent",
                "mapping": {"secret": "not flattened"},
                "mixed": [1, "two"],
                "empty": [],
                "none": None,
            },
        )
    )

    assert set(tracer.spans[0].attributes) == {
        "numa.execution.id",
        "numa.component.name",
        "numa.component.type",
        "numa.lifecycle.status",
    }


def test_adapter_always_ends_span_when_status_mapping_fails() -> None:
    tracer = FailingStatusTracer()
    exporter = OpenTelemetrySpanExporter(tracer, error_status="ERROR")

    with pytest.raises(RuntimeError, match="status unavailable"):
        exporter.export(SpanRecord("numa.agent.failed", "task", "agent", "failed"))

    assert tracer.spans[0].ended


def test_adapter_completes_runtime_integration_without_payload_attributes() -> None:
    tracer = RecordingTracer()
    runtime = AgentRuntime(
        event_bus=EventBus(
            [EventSpanHandler(OpenTelemetrySpanExporter(tracer, error_status="ERROR"))]
        )
    )
    secret = "private task description"

    result = runtime.run(EchoAgent(), Task(description=secret))

    assert result.content == secret
    assert [span.name for span in tracer.spans] == [
        "numa.agent.started",
        "numa.agent.completed",
    ]
    assert all(secret not in repr(span.attributes) for span in tracer.spans)
    assert all(span.ended for span in tracer.spans)


def test_factory_builds_exporter_from_opentelemetry_api(monkeypatch: pytest.MonkeyPatch) -> None:
    tracer = RecordingTracer()
    provider = object()
    calls: list[tuple[str, object]] = []

    def get_tracer(name: str, tracer_provider: object | None = None) -> RecordingTracer:
        calls.append((name, tracer_provider))
        return tracer

    fake_trace = SimpleNamespace(
        Status=lambda code: ("status", code),
        StatusCode=SimpleNamespace(ERROR="error-code"),
        get_tracer=get_tracer,
    )
    monkeypatch.setattr(_MODULE, "import_module", lambda name: fake_trace)

    exporter = create_opentelemetry_exporter("numa.test", tracer_provider=provider)

    assert exporter.tracer is tracer
    assert exporter.error_status == ("status", "error-code")
    assert calls == [("numa.test", provider)]


def test_factory_reports_missing_optional_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_import(name: str) -> Any:
        raise ImportError(name)

    monkeypatch.setattr(_MODULE, "import_module", fail_import)

    with pytest.raises(RuntimeError, match="opentelemetry-sdk"):
        create_opentelemetry_exporter()


def test_factory_rejects_empty_instrumentation_name() -> None:
    with pytest.raises(ValueError, match="instrumentation_name"):
        create_opentelemetry_exporter(" ")
