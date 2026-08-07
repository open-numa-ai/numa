"""Versioned JSON codec for persisted Task records."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, cast

from numa.core import (
    Context,
    Message,
    MessageRole,
    Task,
    TaskPersistenceError,
    TaskStatus,
)
from numa.tasks.base import TaskRecord

SCHEMA_VERSION = 1


def encode_record(record: TaskRecord) -> str:
    """Serialize a Task record to versioned JSON."""
    payload = {
        "schema_version": SCHEMA_VERSION,
        "agent_name": record.agent_name,
        "task": {
            "description": record.task.description,
            "id": record.task.id,
            "metadata": record.task.metadata,
            "status": record.task.status.value,
            "result": _encode_message(record.task.result),
            "error": record.task.error,
        },
        "context": {
            "messages": [_encode_message(message) for message in record.context.messages],
            "metadata": record.context.metadata,
        },
        "updated_at": record.updated_at.isoformat(),
    }
    try:
        return json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise TaskPersistenceError(
            f"Task {record.task.id!r} contains values that are not JSON serializable"
        ) from exc


def decode_record(serialized: str) -> TaskRecord:
    """Deserialize and validate a versioned Task record."""
    try:
        payload = cast(dict[str, Any], json.loads(serialized))
        if payload["schema_version"] != SCHEMA_VERSION:
            raise ValueError("unsupported schema version")
        task_data = cast(dict[str, Any], payload["task"])
        context_data = cast(dict[str, Any], payload["context"])
        result_data = cast(dict[str, Any] | None, task_data["result"])
        task = Task(
            description=str(task_data["description"]),
            id=str(task_data["id"]),
            metadata=cast(dict[str, Any], task_data["metadata"]),
            status=TaskStatus(task_data["status"]),
            result=_decode_message(result_data) if result_data is not None else None,
            error=cast(str | None, task_data["error"]),
        )
        messages = [
            _decode_message(cast(dict[str, Any], message_data))
            for message_data in cast(list[dict[str, Any]], context_data["messages"])
        ]
        return TaskRecord(
            agent_name=str(payload["agent_name"]),
            task=task,
            context=Context(
                messages=messages,
                metadata=cast(dict[str, Any], context_data["metadata"]),
            ),
            updated_at=datetime.fromisoformat(str(payload["updated_at"])),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise TaskPersistenceError("Stored Task record is invalid or unsupported") from exc


def clone_record(record: TaskRecord) -> TaskRecord:
    """Return a detached copy through the persistence representation."""
    return decode_record(encode_record(record))


def _encode_message(message: Message | None) -> dict[str, Any] | None:
    if message is None:
        return None
    return {
        "role": message.role.value,
        "content": message.content,
        "metadata": message.metadata,
        "created_at": message.created_at.isoformat(),
    }


def _decode_message(data: dict[str, Any]) -> Message:
    return Message(
        role=MessageRole(data["role"]),
        content=str(data["content"]),
        metadata=cast(dict[str, Any], data["metadata"]),
        created_at=datetime.fromisoformat(str(data["created_at"])),
    )
