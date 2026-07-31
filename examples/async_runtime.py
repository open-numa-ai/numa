"""Run concurrent Agents and an asynchronous Tool."""

import asyncio

from numa import AsyncAgentRuntime, Task
from numa.agents import AsyncEchoAgent
from numa.tools import AsyncAddTool


async def main() -> None:
    """Execute deterministic asynchronous components."""
    runtime = AsyncAgentRuntime()
    runtime.register_tool(AsyncAddTool())

    messages = await runtime.gather(
        (AsyncEchoAgent(), Task(description="first task")),
        (AsyncEchoAgent(), Task(description="second task")),
    )
    total = await runtime.execute_tool("async_add", left=2, right=3)

    print([message.content for message in messages])
    print(total)


if __name__ == "__main__":
    asyncio.run(main())