"""Shared workflow composition contracts and result models."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from numa.core import Context, Message, Task


@dataclass(frozen=True, slots=True)
class WorkflowStepResult:
    """Capture one completed Agent step and its child Task."""

    name: str
    task: Task
    message: Message


@dataclass(frozen=True, slots=True)
class WorkflowState:
    """Expose a point-in-time workflow view to factories and conditions."""

    task: Task
    context: Context
    results: Mapping[str, WorkflowStepResult]

    def result(self, name: str) -> WorkflowStepResult:
        """Return a completed step result by its stable workflow name."""
        return self.results[name]


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    """Return ordered step outcomes from one workflow execution."""

    task: Task
    context: Context
    steps: tuple[WorkflowStepResult, ...]

    @property
    def final_message(self) -> Message | None:
        """Return the last completed step message, if the workflow produced one."""
        if not self.steps:
            return None
        return self.steps[-1].message

    def result(self, name: str) -> WorkflowStepResult:
        """Return a completed step result by its stable workflow name."""
        for step in self.steps:
            if step.name == name:
                return step
        raise KeyError(name)


WorkflowTaskFactory = Callable[[WorkflowState], Task]
WorkflowCondition = Callable[[WorkflowState], bool]


class WorkflowExecutionState:
    """Mutable execution state shared internally by composed workflow nodes."""

    def __init__(self, task: Task, context: Context) -> None:
        self.task = task
        self.context = context
        self.results: dict[str, WorkflowStepResult] = {}

    def snapshot(self) -> WorkflowState:
        """Create a stable result mapping for user callbacks."""
        return WorkflowState(
            task=self.task,
            context=self.context,
            results=MappingProxyType(dict(self.results)),
        )

    def add_result(self, result: WorkflowStepResult) -> None:
        """Record a result while enforcing stable step identities."""
        if result.name in self.results:
            raise ValueError(f"Duplicate workflow step name: {result.name!r}")
        self.results[result.name] = result

    def build_result(self) -> WorkflowResult:
        """Build the immutable public result in execution order."""
        return WorkflowResult(
            task=self.task,
            context=self.context,
            steps=tuple(self.results.values()),
        )

    def fork(self) -> WorkflowExecutionState:
        """Fork state for an isolated asynchronous branch."""
        branch = WorkflowExecutionState(
            task=self.task,
            context=Context(
                messages=list(self.context.messages),
                metadata=dict(self.context.metadata),
            ),
        )
        branch.results.update(self.results)
        return branch


def build_step_task(
    *,
    name: str,
    state: WorkflowExecutionState,
    task_factory: WorkflowTaskFactory | None,
) -> Task:
    """Build a child Task with workflow correlation metadata."""
    if task_factory is not None:
        task = task_factory(state.snapshot())
        if not isinstance(task, Task):
            raise TypeError(f"Task factory for workflow step {name!r} must return a Task")
    else:
        task = Task(
            description=state.task.description,
            metadata=dict(state.task.metadata),
        )

    task.metadata["workflow_id"] = state.task.id
    task.metadata["workflow_step"] = name
    return task


def validate_step_name(name: str) -> None:
    """Reject ambiguous public step identities."""
    if not isinstance(name, str) or not name:
        raise ValueError("Workflow step name must be a non-empty string")


def validate_unique_step_names(step_names: tuple[str, ...]) -> None:
    """Reject compositions whose possible branches reuse a step name."""
    seen: set[str] = set()
    for name in step_names:
        if name in seen:
            raise ValueError(f"Duplicate workflow step name: {name!r}")
        seen.add(name)
