"""SQLite-backed persistent memory adapter."""

from __future__ import annotations

import json
import sqlite3
from contextlib import suppress
from pathlib import Path
from threading import RLock
from types import TracebackType
from typing import Any

from numa.core import MemoryError
from numa.memory.base import Memory


class SQLiteMemory(Memory):
    """Persist JSON-compatible values in a local SQLite database."""

    def __init__(self, database: str | Path) -> None:
        self._database = str(database)
        self._lock = RLock()
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(self._database, check_same_thread=False)
            connection.execute(
                "CREATE TABLE IF NOT EXISTS memory (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            connection.commit()
        except sqlite3.Error as exc:
            if connection is not None:
                with suppress(sqlite3.Error):
                    connection.close()
            raise MemoryError(f"Could not open SQLite memory: {self._database}") from exc
        assert connection is not None
        self._connection = connection

    def get(self, key: str) -> Any | None:
        with self._lock:
            try:
                row = self._connection.execute(
                    "SELECT value FROM memory WHERE key = ?",
                    (key,),
                ).fetchone()
            except sqlite3.Error as exc:
                raise MemoryError(f"Could not read memory key {key!r}") from exc

        if row is None:
            return None
        try:
            return json.loads(row[0])
        except (TypeError, json.JSONDecodeError) as exc:
            raise MemoryError(f"Stored value for key {key!r} is invalid JSON") from exc

    def set(self, key: str, value: Any) -> None:
        try:
            serialized = json.dumps(value, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise MemoryError(f"Value for key {key!r} is not JSON serializable") from exc

        with self._lock:
            try:
                self._connection.execute(
                    """
                    INSERT INTO memory (key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, serialized),
                )
                self._connection.commit()
            except sqlite3.Error as exc:
                with suppress(sqlite3.Error):
                    self._connection.rollback()
                raise MemoryError(f"Could not store memory key {key!r}") from exc

    def delete(self, key: str) -> bool:
        with self._lock:
            try:
                cursor = self._connection.execute("DELETE FROM memory WHERE key = ?", (key,))
                self._connection.commit()
            except sqlite3.Error as exc:
                with suppress(sqlite3.Error):
                    self._connection.rollback()
                raise MemoryError(f"Could not delete memory key {key!r}") from exc
        return cursor.rowcount > 0

    def clear(self) -> None:
        with self._lock:
            try:
                self._connection.execute("DELETE FROM memory")
                self._connection.commit()
            except sqlite3.Error as exc:
                with suppress(sqlite3.Error):
                    self._connection.rollback()
                raise MemoryError("Could not clear SQLite memory") from exc

    def close(self) -> None:
        """Close the underlying database connection."""
        with self._lock:
            try:
                self._connection.close()
            except sqlite3.Error as exc:
                raise MemoryError("Could not close SQLite memory") from exc

    def __enter__(self) -> SQLiteMemory:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        self.close()