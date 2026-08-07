from datetime import UTC, datetime
from pathlib import Path

import pytest

from numa.core import (
    Context,
    Message,
    MessageRole,
    Task,
    TaskPersistenceError,
    TaskStatus,
)
from numa.tasks import InMemoryTaskStore, SQLiteTaskStore, TaskRecord, TaskStore


def create_record(task_id: str = "task-1") -> TaskRecord:
    message = Message(
        role=MessageRole.ASSISTANT,
        content="done",
        metadata={"tokens": 3},
        created_at=datetime(2026, 1, 2, 3, 4, tzinfo=UTC),
    )
    return TaskRecord(
        agent_name="example_agent",
        task=Task(
            description="persist me",
            id=task_id,
            metadata={"priority": 1},
            status=TaskStatus.COMPLETED,
            result=message,
        ),
        context=Context(messages=[message], metadata={"session": "test"}),
        updated_at=datetime(2026, 1, 2, 3, 5, tzinfo=UTC),
    )


@pytest.mark.parametrize("store", [InMemoryTaskStore()])
def test_task_store_returns_detached_snapshots(store: TaskStore) -> None:
    record = create_record()
    store.save(record)

    record.task.description = "changed after save"
    loaded = store.load(record.task.id)

    assert loaded is not None
    assert loaded.task.description == "persist me"
    loaded.context.metadata["session"] = "changed after load"
    assert store.load(record.task.id) == create_record()


def test_sqlite_task_store_survives_reopen(tmp_path: Path) -> None:
    database = tmp_path / "tasks.db"
    with SQLiteTaskStore(database) as store:
        store.save(create_record("second"))
        store.save(create_record("first"))

    with SQLiteTaskStore(database) as reopened:
        records = reopened.list()
        loaded = reopened.load("first")

        assert [record.task.id for record in records] == ["first", "second"]
        assert loaded == create_record("first")
        assert reopened.delete("first") is True
        assert reopened.delete("first") is False


def test_task_store_rejects_non_json_metadata() -> None:
    record = create_record()
    record.task.metadata["invalid"] = object()

    with pytest.raises(TaskPersistenceError, match="not JSON serializable"):
        InMemoryTaskStore().save(record)


def test_sqlite_task_store_rejects_invalid_record(tmp_path: Path) -> None:
    database = tmp_path / "tasks.db"
    with SQLiteTaskStore(database) as store:
        store._connection.execute(  # type: ignore[attr-defined]
            "INSERT INTO tasks (id, updated_at, record) VALUES (?, ?, ?)",
            ("broken", "2026-01-01T00:00:00+00:00", "not-json"),
        )
        store._connection.commit()  # type: ignore[attr-defined]

        with pytest.raises(TaskPersistenceError, match="invalid or unsupported"):
            store.load("broken")
