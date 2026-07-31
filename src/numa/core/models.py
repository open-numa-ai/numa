"""Framework-neutral data models shared across Numa components."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class MessageRole(StrEnum):
    """Origin of a message in an agent conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class TaskStatus(StrEnum):
    """Lifecycle state for a task executed by a runtime."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Message:
    """A single unit of communication passed through an agent context."""

    role: MessageRole
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class Task:
    """A unit of work submitted to an agent."""

    description: str
    id: str = field(default_factory=lambda: str(uuid4()))
    metadata: dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Message | None = None
    error: str | None = None


@dataclass(slots=True)
class Context:
    """Mutable execution context shared for the lifetime of one task."""

    messages: list[Message] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_message(self, message: Message) -> None:
        """Append a message to the ordered conversation history."""
        self.messages.append(message)
