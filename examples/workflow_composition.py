"""Compose synchronous Agent steps with shared context and a condition."""

from numa import AgentRuntime, AgentStep, ConditionalWorkflow, SequentialWorkflow, Task
from numa.agents import EchoAgent


def main() -> None:
    workflow = SequentialWorkflow(
        [
            AgentStep(EchoAgent(), name="draft"),
            ConditionalWorkflow(
                lambda state: bool(state.result("draft").message.content),
                AgentStep(
                    EchoAgent(),
                    name="review",
                    task_factory=lambda state: Task(
                        description=f"Review: {state.result('draft').message.content}"
                    ),
                ),
            ),
        ]
    )
    result = workflow.run(AgentRuntime(), Task(description="Write a short project update"))
    print([step.message.content for step in result.steps])


if __name__ == "__main__":
    main()
