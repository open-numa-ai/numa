from __future__ import annotations

from typing import Any

import pytest

from numa.agents import LLMAgent
from numa.core import Context, Message, MessageRole, Task
from numa.providers import ModelProvider, ModelRequest, ModelResponse


class RecordingProvider(ModelProvider):
    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    @property
    def name(self) -> str:
        return "recording"

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(
            message=Message(
                role=MessageRole.ASSISTANT,
                content="model response",
                metadata={"provider": self.name},
            ),
            model=request.model,
        )


def test_llm_agent_builds_request_from_prompt_context_and_task() -> None:
    provider = RecordingProvider()
    parameters: dict[str, Any] = {"temperature": 0.2}
    request_metadata: dict[str, Any] = {"tenant": "example"}
    agent = LLMAgent(
        provider,
        name="support",
        system_prompt="Answer concisely.",
        model="example-model",
        parameters=parameters,
        request_metadata=request_metadata,
    )
    history = Message(role=MessageRole.USER, content="Previous question")
    context = Context(messages=[history])
    task = Task(description="Current question", id="task-123")

    result = agent.run(task, context)

    assert agent.name == "support"
    assert result.content == "model response"
    assert result.metadata == {"provider": "recording"}
    assert context.messages == [history]
    assert len(provider.requests) == 1
    request = provider.requests[0]
    assert [(message.role, message.content) for message in request.messages] == [
        (MessageRole.SYSTEM, "Answer concisely."),
        (MessageRole.USER, "Previous question"),
        (MessageRole.USER, "Current question"),
    ]
    assert request.model == "example-model"
    assert request.parameters == {"temperature": 0.2}
    assert request.metadata == {"tenant": "example", "execution_id": "task-123"}


def test_llm_agent_uses_minimal_request_by_default() -> None:
    provider = RecordingProvider()
    task = Task(description="Hello", id="task-456")

    result = LLMAgent(provider).run(task, Context())

    assert result.role is MessageRole.ASSISTANT
    request = provider.requests[0]
    assert [(message.role, message.content) for message in request.messages] == [
        (MessageRole.USER, "Hello")
    ]
    assert request.model is None
    assert request.parameters == {}
    assert request.metadata == {"execution_id": "task-456"}


def test_llm_agent_copies_request_configuration() -> None:
    provider = RecordingProvider()
    parameters: dict[str, Any] = {"stop": ["END"]}
    request_metadata: dict[str, Any] = {
        "execution_id": "caller-value",
        "tags": ["example"],
    }
    agent = LLMAgent(
        provider,
        parameters=parameters,
        request_metadata=request_metadata,
    )
    parameters["temperature"] = 1
    request_metadata["tenant"] = "changed"

    agent.run(Task(description="Hello", id="task-id"), Context())

    assert provider.requests[0].parameters == {"stop": ["END"]}
    assert provider.requests[0].metadata == {
        "execution_id": "task-id",
        "tags": ["example"],
    }


def test_llm_agent_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="name must not be empty"):
        LLMAgent(RecordingProvider(), name="")
