"""Call a provider-neutral model interface without network access."""

from numa import Message, MessageRole, ModelRequest
from numa.providers import EchoModelProvider


def main() -> None:
    """Generate a deterministic response through the provider contract."""
    provider = EchoModelProvider()
    request = ModelRequest(
        messages=(Message(role=MessageRole.USER, content="Hello, Numa"),),
        parameters={"temperature": 0},
    )

    response = provider.generate(request)
    print(response.message.content)


if __name__ == "__main__":
    main()
