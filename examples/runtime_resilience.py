"""Apply deterministic retry policy to asynchronous Agent execution."""

import asyncio

from numa import AsyncAgentRuntime, ResiliencePolicy, RetryPolicy, Task
from numa.agents import AsyncAgent
from numa.core import Context, Message, MessageRole


class FlakyAgent(AsyncAgent):
    """Fail once before returning a deterministic response."""

    def __init__(self) -> None:
        self.attempts = 0

    @property
    def name(self) -> str:
        return "flaky"

    async def run(self, task: Task, context: Context) -> Message:
        del context
        self.attempts += 1
        if self.attempts == 1:
            raise ConnectionError("temporary failure")
        return Message(role=MessageRole.ASSISTANT, content=task.description)


async def main() -> None:
    """Retry one transient Agent failure within a total timeout."""
    policy = ResiliencePolicy(
        timeout_seconds=1,
        retry=RetryPolicy(
            max_attempts=2,
            retry_exceptions=(ConnectionError,),
        ),
    )
    runtime = AsyncAgentRuntime(resilience_policy=policy)
    agent = FlakyAgent()

    result = await runtime.run(agent, Task(description="completed after retry"))
    print(result.content, agent.attempts)


if __name__ == "__main__":
    asyncio.run(main())