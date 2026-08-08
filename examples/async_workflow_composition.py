"""Compose concurrent asynchronous Agent branches."""

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


if __name__ == "__main__":
    asyncio.run(main())
