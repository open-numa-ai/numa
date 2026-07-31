from __future__ import annotations

import pytest

from numa.agents import Agent, EchoAgent
from numa.core import AgentExecutionError, Context, Message, Task, TaskStatus
from numa.runtime import AgentRuntime


class FailingAgent(Agent):
    @property
    def name(self) -> str:
        return "failing"

    def run(self, task: Task, context: Context) -> Message:
        del task, context
        raise ValueError("failure from agent")


def test_runtime_completes_task_and_updates_context() -> None:
    runtime = AgentRuntime()
    task = Task(description="echo this")
    context = Context()

    result = runtime.run(EchoAgent(), task, context)

    assert result.content == "echo this"
    assert task.status is TaskStatus.COMPLETED
    assert task.result is result
    assert context.messages == [result]


def test_runtime_wraps_agent_errors() -> None:
    task = Task(description="fail")

    with pytest.raises(AgentExecutionError, match="failing"):
        AgentRuntime().run(FailingAgent(), task)

    assert task.status is TaskStatus.FAILED
    assert task.error == "failure from agent"
