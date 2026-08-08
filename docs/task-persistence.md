# Task Persistence and Resume

Numa can persist Agent Task lifecycle snapshots and recover unfinished work through an explicit `TaskStore` boundary. Persistence is opt-in and applies to synchronous and asynchronous Runtimes.

## Configure a Store

Use `InMemoryTaskStore` for tests or `SQLiteTaskStore` for local durability:

```python
from numa import AgentRuntime, Task
from numa.agents import EchoAgent
from numa.tasks import SQLiteTaskStore

with SQLiteTaskStore("numa-tasks.db") as store:
    runtime = AgentRuntime(task_store=store)
    task = Task(description="persist this task")
    runtime.run(EchoAgent(), task)
```

The Runtime saves snapshots after transitions to `RUNNING`, `COMPLETED`, `FAILED`, and `CANCELLED`. Each record contains the Task, its Context, the owning Agent name, an update timestamp, and a versioned JSON representation.

Task and Context metadata must be JSON-compatible. Invalid values raise `TaskPersistenceError`. SQLite access is transaction-protected and safe for threads within one process; close the Store explicitly or use it as a context manager.

## Resume a Task

Create a new Runtime with the same Store and provide the Agent that originally owned the Task:

```python
with SQLiteTaskStore("numa-tasks.db") as store:
    runtime = AgentRuntime(task_store=store)
    result = runtime.resume(EchoAgent(), task_id)
```

`AsyncAgentRuntime.resume()` provides the equivalent awaitable API and accepts an optional per-call resilience policy.

Resume behavior depends on the persisted status:

- `COMPLETED` returns the stored result without calling the Agent again.
- `PENDING`, `RUNNING`, `FAILED`, and `CANCELLED` execute the Agent again with the same Task ID and persisted Context.
- Missing Tasks raise `TaskNotFoundError`.
- Agent name mismatches and malformed completed records raise `TaskResumeError`.

Before re-execution, stale result and error fields are cleared. Normal Runtime lifecycle events and resilience policies then apply to the new attempt.

## Recovery Boundary

Resume replays the Agent invocation from its beginning. It does not restore a Python stack, coroutine instruction pointer, open network connection, or in-flight Tool call. Agent operations that can be repeated should use idempotency keys, usually the stable Task ID, and external side effects should be committed atomically or checked before replay.

The built-in Store keeps the latest snapshot for each Task ID. It does not provide history, distributed leases, worker ownership, automatic startup scanning, or exactly-once execution guarantees.