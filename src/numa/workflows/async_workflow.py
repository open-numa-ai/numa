"""Asynchronous workflow nodes composed above AsyncAgentRuntime."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass

from numa.agents import AsyncAgent
from numa.core import Context, Task, TaskStatus, WorkflowExecutionError
from numa.runtime import AsyncAgentRuntime, ResiliencePolicy
from numa.workflows.base import (
    WorkflowCondition,
    WorkflowExecutionState,
    WorkflowResult,
    WorkflowStepResult,
    WorkflowTaskFactory,
    build_step_task,
    validate_step_name,
    validate_unique_step_names,
)


class AsyncWorkflowNode(ABC):
    """An asynchronous node that can run alone or inside another workflow."""

    @property
    @abstractmethod
    def step_names(self) -> tuple[str, ...]:
        """Return every step name that this node may execute."""

    async def run(
        self,
        runtime: AsyncAgentRuntime,
        task: Task,
        context: Context | None = None,
    ) -> WorkflowResult:
        """Execute this node as a top-level asynchronous workflow."""
        execution = WorkflowExecutionState(task, context or Context())
        task.status = TaskStatus.RUNNING
        task.result = None
        task.error = None
        try:
            await self._execute(runtime, execution)
        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            task.error = "Workflow execution cancelled"
            raise
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            if isinstance(exc, WorkflowExecutionError):
                raise
            raise WorkflowExecutionError("Workflow execution failed") from exc

        result = execution.build_result()
        task.result = result.final_message
        task.status = TaskStatus.COMPLETED
        return result

    @abstractmethod
    async def _execute(
        self,
        runtime: AsyncAgentRuntime,
        state: WorkflowExecutionState,
    ) -> None:
        """Execute this node into existing workflow state."""


@dataclass(frozen=True, slots=True)
class AsyncAgentStep(AsyncWorkflowNode):
    """Execute one asynchronous Agent through AsyncAgentRuntime."""

    agent: AsyncAgent
    name: str | None = None
    task_factory: WorkflowTaskFactory | None = None
    resilience_policy: ResiliencePolicy | None = None

    def __post_init__(self) -> None:
        resolved_name = self.agent.name if self.name is None else self.name
        validate_step_name(resolved_name)
        object.__setattr__(self, "name", resolved_name)

    @property
    def step_names(self) -> tuple[str, ...]:
        assert self.name is not None
        return (self.name,)

    async def _execute(
        self,
        runtime: AsyncAgentRuntime,
        state: WorkflowExecutionState,
    ) -> None:
        assert self.name is not None
        if self.name in state.results:
            raise WorkflowExecutionError(f"Duplicate workflow step name: {self.name!r}")
        step_task = build_step_task(
            name=self.name,
            state=state,
            task_factory=self.task_factory,
        )
        try:
            message = await runtime.run(
                self.agent,
                step_task,
                state.context,
                resilience_policy=self.resilience_policy,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise WorkflowExecutionError(f"Workflow step {self.name!r} failed") from exc
        state.add_result(WorkflowStepResult(self.name, step_task, message))


class AsyncSequentialWorkflow(AsyncWorkflowNode):
    """Execute asynchronous workflow nodes in declaration order."""

    def __init__(self, nodes: Iterable[AsyncWorkflowNode]) -> None:
        self.nodes = tuple(nodes)
        if not self.nodes:
            raise ValueError("Sequential workflow requires at least one node")
        validate_unique_step_names(self.step_names)

    @property
    def step_names(self) -> tuple[str, ...]:
        return tuple(name for node in self.nodes for name in node.step_names)

    async def _execute(
        self,
        runtime: AsyncAgentRuntime,
        state: WorkflowExecutionState,
    ) -> None:
        for node in self.nodes:
            await node._execute(runtime, state)


class AsyncParallelWorkflow(AsyncWorkflowNode):
    """Execute isolated branches concurrently and merge them deterministically."""

    def __init__(self, branches: Iterable[AsyncWorkflowNode]) -> None:
        self.branches = tuple(branches)
        if not self.branches:
            raise ValueError("Parallel workflow requires at least one branch")
        validate_unique_step_names(self.step_names)

    @property
    def step_names(self) -> tuple[str, ...]:
        return tuple(name for branch in self.branches for name in branch.step_names)

    async def _execute(
        self,
        runtime: AsyncAgentRuntime,
        state: WorkflowExecutionState,
    ) -> None:
        existing_names = frozenset(state.results)
        overlapping = existing_names.intersection(self.step_names)
        if overlapping:
            duplicate = sorted(overlapping)[0]
            raise WorkflowExecutionError(f"Duplicate workflow step name: {duplicate!r}")

        initial_message_count = len(state.context.messages)
        branch_states: list[WorkflowExecutionState | None] = [None] * len(self.branches)

        async def execute_branch(index: int, branch: AsyncWorkflowNode) -> None:
            branch_state = state.fork()
            await branch._execute(runtime, branch_state)
            branch_states[index] = branch_state

        try:
            async with asyncio.TaskGroup() as group:
                for index, branch in enumerate(self.branches):
                    group.create_task(execute_branch(index, branch))
        except ExceptionGroup as exc:
            raise WorkflowExecutionError("Parallel workflow branch failed") from exc

        for branch_state in branch_states:
            assert branch_state is not None
            for name, result in branch_state.results.items():
                if name not in existing_names:
                    state.add_result(result)
            state.context.messages.extend(branch_state.context.messages[initial_message_count:])


class AsyncConditionalWorkflow(AsyncWorkflowNode):
    """Execute one asynchronous branch selected from current workflow state."""

    def __init__(
        self,
        condition: WorkflowCondition,
        when_true: AsyncWorkflowNode,
        when_false: AsyncWorkflowNode | None = None,
    ) -> None:
        self.condition = condition
        self.when_true = when_true
        self.when_false = when_false
        validate_unique_step_names(self.step_names)

    @property
    def step_names(self) -> tuple[str, ...]:
        false_names = () if self.when_false is None else self.when_false.step_names
        return self.when_true.step_names + false_names

    async def _execute(
        self,
        runtime: AsyncAgentRuntime,
        state: WorkflowExecutionState,
    ) -> None:
        try:
            selected = self.when_true if self.condition(state.snapshot()) else self.when_false
        except Exception as exc:
            raise WorkflowExecutionError("Workflow condition evaluation failed") from exc
        if selected is not None:
            await selected._execute(runtime, state)
