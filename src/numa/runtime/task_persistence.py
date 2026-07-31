"""Shared Runtime helpers for Task persistence and recovery."""

from __future__ import annotations

from numa.core import (
    Context,
    Task,
    TaskNotFoundError,
    TaskResumeError,
    TaskStatus,
)
from numa.tasks import TaskRecord, TaskStore


def persist_task(
    task_store: TaskStore | None,
    agent_name: str,
    task: Task,
    context: Context,
) -> None:
    """Persist the current execution snapshot when a Store is configured."""
    if task_store is not None:
        task_store.save(TaskRecord(agent_name=agent_name, task=task, context=context))


def load_task_for_resume(
    task_store: TaskStore | None,
    task_id: str,
    agent_name: str,
) -> TaskRecord:
    """Load a snapshot and verify that its original Agent will resume it."""
    if task_store is None:
        raise TaskResumeError("Task resume requires a configured TaskStore")
    record = task_store.load(task_id)
    if record is None:
        raise TaskNotFoundError(f"Task {task_id!r} is not persisted")
    if record.agent_name != agent_name:
        raise TaskResumeError(
            f"Task {task_id!r} belongs to Agent {record.agent_name!r}, not {agent_name!r}"
        )
    if record.task.status is TaskStatus.COMPLETED and record.task.result is None:
        raise TaskResumeError(f"Completed Task {task_id!r} has no persisted result")
    return record