from dataclasses import FrozenInstanceError

import pytest

from numa.core import Message, MessageRole
from numa.providers import (
    EchoModelProvider,
    ModelProvider,
    ModelProviderExecutionError,
    ModelRequest,
    ModelResponse,
    ModelUsage,
)


def test_model_provider_is_abstract() -> None:
    with pytest.raises(TypeError):
        ModelProvider()  # type: ignore[abstract]


def test_model_request_is_immutable() -> None:
    request = ModelRequest(
        messages=(Message(role=MessageRole.USER, content="hello"),),
        model="test-model",
    )

    with pytest.raises(FrozenInstanceError):
        request.model = "other"  # type: ignore[misc]


def test_model_usage_reports_total_tokens() -> None:
    usage = ModelUsage(input_tokens=10, output_tokens=4)

    assert usage.total_tokens == 14


def test_echo_provider_returns_provider_neutral_response() -> None:
    provider = EchoModelProvider()
    request = ModelRequest(
        messages=(
            Message(role=MessageRole.SYSTEM, content="Be concise"),
            Message(role=MessageRole.USER, content="Hello, Numa"),
        ),
        parameters={"temperature": 0},
        metadata={"request_id": "test"},
    )

    response = provider.generate(request)

    assert isinstance(response, ModelResponse)
    assert response.message.role is MessageRole.ASSISTANT
    assert response.message.content == "Hello, Numa"
    assert response.message.metadata == {"source_role": "user"}
    assert response.model == "echo"
    assert response.metadata == {"provider": "echo"}
    assert request.parameters == {"temperature": 0}


def test_echo_provider_preserves_requested_model_name() -> None:
    response = EchoModelProvider().generate(
        ModelRequest(
            messages=(Message(role=MessageRole.USER, content="hello"),),
            model="custom-model",
        )
    )

    assert response.model == "custom-model"


def test_echo_provider_rejects_empty_request() -> None:
    with pytest.raises(ModelProviderExecutionError, match="at least one message"):
        EchoModelProvider().generate(ModelRequest(messages=()))
