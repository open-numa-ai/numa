"""Run the provider-backed reference Agent without network access."""

from numa import AgentRuntime, Task
from numa.agents import LLMAgent
from numa.providers import EchoModelProvider


def main() -> None:
    """Compose an Agent, provider, and Runtime through public contracts."""
    agent = LLMAgent(
        EchoModelProvider(),
        system_prompt="Answer clearly and concisely.",
        parameters={"temperature": 0},
    )
    result = AgentRuntime().run(agent, Task(description="Hello from Numa"))
    print(result.content)


if __name__ == "__main__":
    main()
