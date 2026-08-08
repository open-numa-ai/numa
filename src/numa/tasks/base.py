"""Task persistence contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime

from numa.core import Context, Task


@dataclass(frozen=True, slots=True)
class TaskRecord:
    """A persisted Task, execution Context, and owning Agent identity."""

    agent_name: str
    task: Task
    context: Context
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class TaskStore(ABC):
    """Persistence boundary for resumable Task snapshots."""

    @abstractmethod
    def save(self, record: TaskRecord) -> None:
        """Create or replace a Task snapshot."""

    @abstractmethod
    def load(self, task_id: str) -> TaskRecord | None:
        """Load a Task snapshot, or return None when absent."""

    @abstractmethod
    def delete(self, task_id: str) -> bool:
        """Delete a Task snapshot and report whether it existed."""

    @abstractmethod
    def list(self) -> tuple[TaskRecord, ...]:
        """Return all Task snapshots ordered by update time and ID."""
