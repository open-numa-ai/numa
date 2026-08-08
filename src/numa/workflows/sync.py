"""Synchronous workflow nodes composed above AgentRuntime."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass

from numa.agents import Agent
from numa.core import Context, Task, TaskStatus, WorkflowExecutionError
from numa.runtime import AgentRuntime
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


class WorkflowNode(ABC):
    """A synchronous node that can run alone or inside another workflow."""

    @property
    @abstractmethod
    def step_names(self) -> tuple[str, ...]:
        """Return every step name that this node may execute."""

    def run(
        self,
        runtime: AgentRuntime,
        task: Task,
        context: Context | None = None,
    ) -> WorkflowResult:
        """Execute this node as a top-level workflow."""
        execution = WorkflowExecutionState(task, context or Context())
        task.status = TaskStatus.RUNNING
        task.result = None
        task.error = None
        try:
            self._execute(runtime, execution)
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
    def _execute(self, runtime: AgentRuntime, state: WorkflowExecutionState) -> None:
        """Execute this node into existing workflow state."""


@dataclass(frozen=True, slots=True)
class AgentStep(WorkflowNode):
    """Execute one synchronous Agent through AgentRuntime."""

    agent: Agent
    name: str | None = None
    task_factory: WorkflowTaskFactory | None = None

    def __post_init__(self) -> None:
        resolved_name = self.agent.name if self.name is None else self.name
        validate_step_name(resolved_name)
        object.__setattr__(self, "name", resolved_name)

    @property
    def step_names(self) -> tuple[str, ...]:
        assert self.name is not None
        return (self.name,)

    def _execute(self, runtime: AgentRuntime, state: WorkflowExecutionState) -> None:
        assert self.name is not None
        if self.name in state.results:
            raise WorkflowExecutionError(f"Duplicate workflow step name: {self.name!r}")
        step_task = build_step_task(
            name=self.name,
            state=state,
            task_factory=self.task_factory,
        )
        try:
            message = runtime.run(self.agent, step_task, state.context)
        except Exception as exc:
            raise WorkflowExecutionError(f"Workflow step {self.name!r} failed") from exc
        state.add_result(WorkflowStepResult(self.name, step_task, message))


class SequentialWorkflow(WorkflowNode):
    """Execute synchronous workflow nodes in declaration order."""

    def __init__(self, nodes: Iterable[WorkflowNode]) -> None:
        self.nodes = tuple(nodes)
        if not self.nodes:
            raise ValueError("Sequential workflow requires at least one node")
        validate_unique_step_names(self.step_names)

    @property
    def step_names(self) -> tuple[str, ...]:
        return tuple(name for node in self.nodes for name in node.step_names)

    def _execute(self, runtime: AgentRuntime, state: WorkflowExecutionState) -> None:
        for node in self.nodes:
            node._execute(runtime, state)


class ConditionalWorkflow(WorkflowNode):
    """Execute one synchronous branch selected from current workflow state."""

    def __init__(
        self,
        condition: WorkflowCondition,
        when_true: WorkflowNode,
        when_false: WorkflowNode | None = None,
    ) -> None:
        self.condition = condition
        self.when_true = when_true
        self.when_false = when_false
        validate_unique_step_names(self.step_names)

    @property
    def step_names(self) -> tuple[str, ...]:
        false_names = () if self.when_false is None else self.when_false.step_names
        return self.when_true.step_names + false_names

    def _execute(self, runtime: AgentRuntime, state: WorkflowExecutionState) -> None:
        try:
            selected = self.when_true if self.condition(state.snapshot()) else self.when_false
        except Exception as exc:
            raise WorkflowExecutionError("Workflow condition evaluation failed") from exc
        if selected is not None:
            selected._execute(runtime, state)
