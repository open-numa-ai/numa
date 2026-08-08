# Tool Permission Policies

Tool permission policies provide an explicit authorization boundary around Runtime-managed Tool
execution. Both `AgentRuntime` and `AsyncAgentRuntime` validate and normalize Tool input, evaluate
the configured policy, and only then enter middleware and the Tool implementation.

## Built-in Policies

Use an allowlist when an application should expose only a known set of capabilities:

```python
from numa import AgentRuntime, ToolAllowlistPolicy
from numa.tools import AddTool

runtime = AgentRuntime(tool_permission_policy=ToolAllowlistPolicy(["add"]))
runtime.register_tool(AddTool())

print(runtime.execute_tool("add", left=2, right=3))
```

Numa also provides:

- `AllowAllToolPolicy`, the backward-compatible Runtime default.
- `DenyAllToolPolicy`, a kill switch for Runtime-managed Tool execution.
- `ToolDenylistPolicy`, which blocks named Tools and allows other registered Tools.

Allowlist and denylist names are normalized to immutable `frozenset` values when the policy is
created. Empty Tool names are rejected.

## Argument-aware Policies

Implement `ToolPermissionPolicy.evaluate()` when a decision depends on normalized arguments or
application policy:

```python
from numa import (
    ToolPermissionDecision,
    ToolPermissionPolicy,
    ToolPermissionRequest,
)


class BoundedAddPolicy(ToolPermissionPolicy):
    def evaluate(self, request: ToolPermissionRequest) -> ToolPermissionDecision:
        if request.tool_name == "add" and request.arguments["left"] <= 10:
            return ToolPermissionDecision.allow()
        return ToolPermissionDecision.deny("operation exceeds its configured scope")
```

The request contains the Tool name, the Runtime execution ID, and a read-only view of normalized
arguments. A policy returns an explicit `ToolPermissionDecision`; truthy values are not treated as
allow decisions.

Policies are synchronous in both Runtime variants. Keep evaluation deterministic and non-blocking,
and load external authorization state before constructing the Runtime. This avoids hiding blocking
I/O in the async event loop and keeps authorization outside resilience retries.

## Failure Semantics

An explicit denial raises `ToolPermissionDeniedError`. If a policy raises or returns an invalid
decision, the Runtime fails closed with `ToolPermissionPolicyError`; the original policy exception
is retained as `__cause__` when applicable.

Denied calls:

- occur after Tool lookup and input validation;
- do not enter Runtime middleware or call the Tool implementation;
- are never retried by async resilience policies;
- emit the normal `TOOL_STARTED` and `TOOL_FAILED` lifecycle events without argument payloads.

Permission evaluation happens before middleware so trusted middleware cannot accidentally weaken
the configured policy by rewriting arguments. Direct calls to `Tool.execute()` remain a low-level
escape hatch and bypass Runtime permissions, validation, events, middleware, and error conversion.

These policies authorize execution but do not sandbox Tool code. Applications remain responsible
for process isolation, filesystem and network controls, credential scoping, and audit retention.
