"""Persist and resume an interrupted Task with SQLite."""

from pathlib import Path

from numa import AgentRuntime, Task
from numa.agents import EchoAgent
from numa.core import Context, TaskStatus
from numa.tasks import SQLiteTaskStore, TaskRecord


def main() -> None:
    """Simulate process recovery from a persisted running snapshot."""
    database = Path("numa-tasks.db")
    task = Task(description="resume after restart", status=TaskStatus.RUNNING)

    with SQLiteTaskStore(database) as store:
        store.save(TaskRecord(agent_name="example_agent", task=task, context=Context()))

    with SQLiteTaskStore(database) as reopened:
        result = AgentRuntime(task_store=reopened).resume(EchoAgent(), task.id)
        print(result.content)


if __name__ == "__main__":
    main()
