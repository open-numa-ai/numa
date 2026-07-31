"""Deterministic model provider used by examples and tests."""

from numa.core import Message, MessageRole
from numa.providers.base import ModelProvider, ModelRequest, ModelResponse
from numa.providers.exceptions import ModelProviderExecutionError


class EchoModelProvider(ModelProvider):
    """Return the final request message without model inference."""

    def __init__(self, default_model: str = "echo") -> None:
        self._default_model = default_model

    @property
    def name(self) -> str:
        return "echo"

    def generate(self, request: ModelRequest) -> ModelResponse:
        if not request.messages:
            raise ModelProviderExecutionError("Echo provider requires at least one message")

        source = request.messages[-1]
        return ModelResponse(
            message=Message(
                role=MessageRole.ASSISTANT,
                content=source.content,
                metadata={"source_role": source.role.value},
            ),
            model=request.model or self._default_model,
            metadata={"provider": self.name},
        )
