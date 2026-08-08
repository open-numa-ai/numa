"""In-memory Task store for local execution and tests."""

from threading import RLock

from numa.tasks.base import TaskRecord, TaskStore
from numa.tasks.codec import clone_record


class InMemoryTaskStore(TaskStore):
    """Store detached Task snapshots in process memory."""

    def __init__(self) -> None:
        self._records: dict[str, TaskRecord] = {}
        self._lock = RLock()

    def save(self, record: TaskRecord) -> None:
        snapshot = clone_record(record)
        with self._lock:
            self._records[record.task.id] = snapshot

    def load(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            record = self._records.get(task_id)
            return clone_record(record) if record is not None else None

    def delete(self, task_id: str) -> bool:
        with self._lock:
            return self._records.pop(task_id, None) is not None

    def list(self) -> tuple[TaskRecord, ...]:
        with self._lock:
            records = sorted(
                self._records.values(),
                key=lambda record: (record.updated_at, record.task.id),
            )
            return tuple(clone_record(record) for record in records)
