# Runtime Resilience Policies

`AsyncAgentRuntime` provides explicit timeout, retry, and cancellation behavior without changing synchronous execution or hiding blocking work in the event loop.

## Defaults

The default `ResiliencePolicy` has no timeout and a `RetryPolicy` with one total attempt. Existing async Runtime calls therefore retain their original behavior.

```python
from numa import AsyncAgentRuntime, ResiliencePolicy, RetryPolicy

policy = ResiliencePolicy(
    timeout_seconds=30,
    retry=RetryPolicy(
        max_attempts=3,
        delay_seconds=0.25,
        backoff_multiplier=2,
        max_delay_seconds=2,
        retry_exceptions=(ConnectionError,),
    ),
)
runtime = AsyncAgentRuntime(resilience_policy=policy)
```

`max_attempts` includes the initial call. Backoff is deterministic and occurs before each retry. The timeout is a total deadline covering all attempts and backoff delays, rather than a fresh timeout for every attempt.

## Per-Call Policies

Override the Runtime default for one Agent execution:

```python
result = await runtime.run(agent, task, resilience_policy=policy)
```

Tool calls use a separate method so a Tool can still declare an input named `resilience_policy`:

```python
result = await runtime.execute_tool_with_policy("fetch", policy, url=url)
```

Input validation, Tool lookup, and output validation occur once and are not retried. Only the asynchronous Agent or Tool implementation call is retried.

Runtime middleware also executes once per public call and wraps the complete resilience operation.
Retries therefore do not repeat middleware side effects. See [Runtime Middleware](runtime-middleware.md)
for ordering and short-circuit behavior.

## Timeout and Cancellation

An Agent deadline raises `AgentTimeoutError`, marks its Task as `FAILED`, and emits `agent.failed`. A Tool deadline raises `ToolTimeoutError` and emits `tool.failed`.

External `asyncio.Task.cancel()` cancellation is never retried or wrapped. Agent cancellation marks its Task as `CANCELLED`; Agent and Tool cancellation emit `agent.cancelled` and `tool.cancelled`, then propagate `asyncio.CancelledError` to the caller.

Retries should be limited to failures known to be transient and operations known to be safe to repeat. Numa does not infer idempotency, compensate side effects, or add random jitter.
