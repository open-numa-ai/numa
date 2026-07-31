"""SQLite-backed persistent Task store."""

from __future__ import annotations

import sqlite3
from contextlib import suppress
from pathlib import Path
from threading import RLock
from types import TracebackType

from numa.core import TaskPersistenceError
from numa.tasks.base import TaskRecord, TaskStore
from numa.tasks.codec import decode_record, encode_record


class SQLiteTaskStore(TaskStore):
    """Persist versioned Task snapshots in a local SQLite database."""

    def __init__(self, database: str | Path) -> None:
        self._database = str(database)
        self._lock = RLock()
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(self._database, check_same_thread=False)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    updated_at TEXT NOT NULL,
                    record TEXT NOT NULL
                )
                """
            )
            connection.commit()
        except sqlite3.Error as exc:
            if connection is not None:
                with suppress(sqlite3.Error):
                    connection.close()
            raise TaskPersistenceError(f"Could not open Task store: {self._database}") from exc
        assert connection is not None
        self._connection = connection

    def save(self, record: TaskRecord) -> None:
        serialized = encode_record(record)
        with self._lock:
            try:
                self._connection.execute(
                    """
                    INSERT INTO tasks (id, updated_at, record) VALUES (?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        updated_at = excluded.updated_at,
                        record = excluded.record
                    """,
                    (record.task.id, record.updated_at.isoformat(), serialized),
                )
                self._connection.commit()
            except sqlite3.Error as exc:
                with suppress(sqlite3.Error):
                    self._connection.rollback()
                raise TaskPersistenceError(f"Could not store Task {record.task.id!r}") from exc

    def load(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            try:
                row = self._connection.execute(
                    "SELECT record FROM tasks WHERE id = ?",
                    (task_id,),
                ).fetchone()
            except sqlite3.Error as exc:
                raise TaskPersistenceError(f"Could not load Task {task_id!r}") from exc
        return decode_record(row[0]) if row is not None else None

    def delete(self, task_id: str) -> bool:
        with self._lock:
            try:
                cursor = self._connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                self._connection.commit()
            except sqlite3.Error as exc:
                with suppress(sqlite3.Error):
                    self._connection.rollback()
                raise TaskPersistenceError(f"Could not delete Task {task_id!r}") from exc
        return cursor.rowcount > 0

    def list(self) -> tuple[TaskRecord, ...]:
        with self._lock:
            try:
                rows = self._connection.execute(
                    "SELECT record FROM tasks ORDER BY updated_at, id"
                ).fetchall()
            except sqlite3.Error as exc:
                raise TaskPersistenceError("Could not list Tasks") from exc
        return tuple(decode_record(row[0]) for row in rows)

    def close(self) -> None:
        """Close the underlying database connection."""
        with self._lock:
            try:
                self._connection.close()
            except sqlite3.Error as exc:
                raise TaskPersistenceError("Could not close Task store") from exc

    def __enter__(self) -> SQLiteTaskStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        self.close()