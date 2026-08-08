# Runtime Middleware

Runtime middleware wraps Agent and Tool component calls without changing their contracts. It can
add cross-cutting behavior such as audit metadata, timing, context enrichment, argument rewriting,
result transformation, or policy enforcement.

## Synchronous Middleware

Implement `RuntimeMiddleware.invoke()` and call `call_next()` to continue the chain:

```python
from typing import Any

from numa import (
    AgentRuntime,
    RuntimeInvocation,
    RuntimeMiddleware,
    RuntimeNext,
    Task,
    ToolInvocation,
)
from numa.agents import EchoAgent


class TenantMiddleware(RuntimeMiddleware):
    def invoke(
        self,
        invocation: RuntimeInvocation,
        call_next: RuntimeNext,
    ) -> Any:
        invocation.metadata["tenant_id"] = "acme"
        return call_next(invocation)


runtime = AgentRuntime(middlewares=[TenantMiddleware()])
result = runtime.run(EchoAgent(), Task(description="Hello"))
```

Use `isinstance(invocation, AgentInvocation)` or `ToolInvocation` when behavior applies to only one
component type. Agent invocations expose the `Task` and `Context`. Tool invocations expose arguments
after input schema validation. Both expose the component name, correlated execution ID, and a
per-invocation metadata dictionary that middleware can share.

## Asynchronous Middleware

Async runtimes require an explicit asynchronous contract:

```python
from typing import Any

from numa import (
    AsyncRuntimeMiddleware,
    AsyncRuntimeNext,
    RuntimeInvocation,
)


class TimingMiddleware(AsyncRuntimeMiddleware):
    async def invoke(
        self,
        invocation: RuntimeInvocation,
        call_next: AsyncRuntimeNext,
    ) -> Any:
        return await call_next(invocation)
```

Pass instances through `AsyncAgentRuntime(middlewares=[...])`. Numa does not adapt synchronous
middleware into the async runtime or hide blocking work in the event loop.

## Ordering and Short-Circuiting

Middleware is ordered. The first registered item is the outermost wrapper:

```text
first before -> second before -> component -> second after -> first after
```

Constructor middleware runs before middleware appended later with `add_middleware()`. The
`middlewares` property returns the current immutable execution order.

A middleware may return without calling `call_next()`. This short-circuits the remaining chain and
the component call. The returned value still passes through the Runtime's normal completion and
Tool output-validation behavior. Raising from middleware follows the same failure, persistence,
event, and exception semantics as raising from the wrapped component.

## Runtime Boundaries

- Tool lookup, input validation, and permission evaluation happen before middleware. Tool output
  validation happens after the complete chain, including short-circuit results. Middleware that
  rewrites normalized Tool arguments is responsible for preserving the Tool's declared input
  contract. Permission policies therefore authorize the pre-middleware normalized arguments.
- Async middleware runs once per public Runtime call. Resilience retries wrap only the terminal
  Agent or Tool implementation, so middleware side effects are not repeated for each attempt.
- Middleware executes inside Agent and Tool lifecycle events. Its execution ID therefore matches
  the corresponding structured event ID.
- Middleware instances are application code with access to task context and normalized Tool
  arguments. Only install trusted middleware and avoid placing secrets in shared metadata.

Use `compose_middleware()` and `compose_async_middleware()` when the same contracts need to wrap a
custom terminal handler outside a Runtime.
