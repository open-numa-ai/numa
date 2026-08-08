"""Add ordered cross-cutting behavior around Runtime component calls."""

from typing import Any

from numa import (
    AgentInvocation,
    AgentRuntime,
    Message,
    MessageRole,
    RuntimeInvocation,
    RuntimeMiddleware,
    RuntimeNext,
    Task,
)
from numa.agents import EchoAgent


class PrefixMiddleware(RuntimeMiddleware):
    """Transform Agent results while leaving Tool calls unchanged."""

    def invoke(self, invocation: RuntimeInvocation, call_next: RuntimeNext) -> Any:
        result = call_next(invocation)
        if isinstance(invocation, AgentInvocation):
            return Message(
                role=MessageRole.ASSISTANT,
                content=f"middleware: {result.content}",
                metadata=result.metadata,
            )
        return result


def main() -> None:
    """Run an Agent through one synchronous middleware wrapper."""
    runtime = AgentRuntime(middlewares=[PrefixMiddleware()])
    result = runtime.run(EchoAgent(), Task(description="Hello from Numa"))
    print(result.content)


if __name__ == "__main__":
    main()
