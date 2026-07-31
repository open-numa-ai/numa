"""Structured lifecycle event models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class EventType(StrEnum):
    """Lifecycle transitions emitted by Numa components."""

    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    TOOL_STARTED = "tool.started"
    TOOL_COMPLETED = "tool.completed"
    TOOL_FAILED = "tool.failed"
    PROVIDER_STARTED = "provider.started"
    PROVIDER_COMPLETED = "provider.completed"
    PROVIDER_FAILED = "provider.failed"


@dataclass(frozen=True, slots=True)
class Event:
    """A structured record of one component lifecycle transition."""

    type: EventType
    execution_id: str
    component_name: str
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
