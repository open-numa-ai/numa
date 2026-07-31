"""Run Numa's minimal agent without any LLM integration."""

from numa import AgentRuntime, Task
from numa.agents import EchoAgent


def main() -> None:
    """Execute a simple task through the runtime."""
    task = Task(description="Numa is ready")
    result = AgentRuntime().run(EchoAgent(), task)
    print(result.content)


if __name__ == "__main__":
    main()
