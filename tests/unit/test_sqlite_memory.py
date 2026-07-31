from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from numa.core import MemoryError
from numa.memory import SQLiteMemory


def test_rejects_database_in_missing_directory(tmp_path: Path) -> None:
    database = tmp_path / "missing" / "memory.db"

    with pytest.raises(MemoryError, match="Could not open"):
        SQLiteMemory(database)


def test_persists_values_across_instances(tmp_path: Path) -> None:
    database = tmp_path / "memory.db"

    with SQLiteMemory(database) as memory:
        memory.set("profile", {"name": "Numa", "topics": ["agents", "memory"]})

    with SQLiteMemory(database) as reopened:
        assert reopened.get("profile") == {
            "name": "Numa",
            "topics": ["agents", "memory"],
        }


def test_overwrites_existing_value(tmp_path: Path) -> None:
    with SQLiteMemory(tmp_path / "memory.db") as memory:
        memory.set("answer", 41)
        memory.set("answer", 42)

        assert memory.get("answer") == 42


def test_delete_reports_stored_none(tmp_path: Path) -> None:
    with SQLiteMemory(tmp_path / "memory.db") as memory:
        memory.set("nullable", None)

        assert memory.get("nullable") is None
        assert memory.delete("nullable") is True
        assert memory.delete("nullable") is False


def test_clear_removes_all_values(tmp_path: Path) -> None:
    with SQLiteMemory(tmp_path / "memory.db") as memory:
        memory.set("first", 1)
        memory.set("second", 2)

        memory.clear()

        assert memory.get("first") is None
        assert memory.get("second") is None


def test_supports_concurrent_writes(tmp_path: Path) -> None:
    with SQLiteMemory(tmp_path / "memory.db") as memory:
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(lambda value: memory.set(f"key-{value}", value), range(20)))

        assert [memory.get(f"key-{value}") for value in range(20)] == list(range(20))


def test_rejects_non_json_serializable_values(tmp_path: Path) -> None:
    with SQLiteMemory(tmp_path / "memory.db") as memory:
        with pytest.raises(MemoryError, match="not JSON serializable"):
            memory.set("unsupported", object())

        with pytest.raises(MemoryError, match="not JSON serializable"):
            memory.set("not-finite", float("nan"))


def test_converts_operations_after_close_to_memory_error(tmp_path: Path) -> None:
    memory = SQLiteMemory(tmp_path / "memory.db")
    memory.close()

    with pytest.raises(MemoryError, match="Could not read"):
        memory.get("answer")
