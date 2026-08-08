# Workflow Composition

Numa workflows compose explicit Agent steps above the existing Runtime boundaries. They provide execution structure without selecting tasks, prompts, models, or branches on behalf of the application.

## Synchronous Sequence

`AgentStep` delegates one child Task to `AgentRuntime`. A `SequentialWorkflow` executes nodes in declaration order and shares one `Context`, so later Agents can observe earlier messages.

```python
from numa import AgentRuntime, AgentStep, SequentialWorkflow, Task
from numa.agents import EchoAgent

workflow = SequentialWorkflow(
    [
        AgentStep(EchoAgent(), name="draft"),
        AgentStep(
            EchoAgent(),
            name="review",
            task_factory=lambda state: Task(
                description=f"Review: {state.result('draft').message.content}"
            ),
        ),
    ]
)

result = workflow.run(AgentRuntime(), Task(description="Write an update"))
print(result.result("draft").message.content)
print(result.final_message)
```

When no `task_factory` is supplied, a step receives a new Task with the root description and metadata. Every child Task adds `workflow_id` and `workflow_step` correlation metadata. Factories receive a `WorkflowState` snapshot containing the root Task, shared Context, and previously completed named results.

## Conditions

Conditions are synchronous, side-effect-free application callbacks. They select one declared branch from the results available at that point.

```python
from numa import AgentStep, ConditionalWorkflow

branch = ConditionalWorkflow(
    lambda state: "approved" in state.result("review").message.content,
    when_true=AgentStep(publish_agent, name="publish"),
    when_false=AgentStep(revise_agent, name="revise"),
)
```

Both possible branches must use distinct step names. A false condition with no `when_false` branch is an explicit no-op.

## Asynchronous Parallel Branches

`AsyncParallelWorkflow` runs explicit `AsyncWorkflowNode` branches with `asyncio.TaskGroup`. A branch failure cancels unfinished siblings. External cancellation remains visible and marks the root workflow Task as cancelled.

```python
import asyncio

from numa import AsyncAgentRuntime, AsyncAgentStep, AsyncParallelWorkflow, Task
from numa.agents import AsyncEchoAgent


async def main() -> None:
    workflow = AsyncParallelWorkflow(
        [
            AsyncAgentStep(AsyncEchoAgent(), name="option_a"),
            AsyncAgentStep(AsyncEchoAgent(), name="option_b"),
        ]
    )
    result = await workflow.run(
        AsyncAgentRuntime(),
        Task(description="Generate an option"),
    )
    print([step.message.content for step in result.steps])


asyncio.run(main())
```

Parallel branches receive isolated copies of the current messages and Context metadata. After every branch succeeds, new results and messages are merged in branch declaration order. Metadata mutations inside a parallel branch are intentionally not merged because concurrent writes have no general conflict-free meaning.

Numa does not run synchronous Agents in hidden worker threads. Parallel composition is therefore available only through `AsyncParallelWorkflow` and explicit `AsyncAgent` implementations.

## Lifecycle and Failure Semantics

- The root Task is marked running, then completed, failed, or cancelled by the workflow.
- Each Agent step uses a separate child Task executed through the supplied Runtime.
- Runtime middleware, events, resilience, permission enforcement, and optional child Task persistence remain active.
- `WorkflowExecutionError` identifies step, condition, or parallel-branch failures and preserves the original exception as its cause.
- Sequential work completed before a later failure is not rolled back.
- The root workflow Task is not automatically stored in the Runtime's `TaskStore`.
- Workflows do not provide exactly-once execution or side-effect compensation.

Step names must be non-empty and unique across every possible branch of one composition. `WorkflowResult.steps` preserves deterministic execution or merge order, and `WorkflowResult.result(name)` retrieves a named outcome.
