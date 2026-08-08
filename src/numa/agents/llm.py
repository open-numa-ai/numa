"""Provider-backed reference Agent implementation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from numa.agents.base import Agent
from numa.core import Context, Message, MessageRole, Task
from numa.providers import ModelProvider, ModelRequest


class LLMAgent(Agent):
    """Generate one response through a provider-neutral model boundary."""

    def __init__(
        self,
        provider: ModelProvider,
        *,
        name: str = "llm_agent",
        system_prompt: str | None = None,
        model: str | None = None,
        parameters: Mapping[str, Any] | None = None,
        request_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        if not name:
            raise ValueError("LLM Agent name must not be empty")

        self._provider = provider
        self._name = name
        self._system_prompt = system_prompt
        self._model = model
        self._parameters = dict(parameters or {})
        self._request_metadata = dict(request_metadata or {})

    @property
    def name(self) -> str:
        """Return the configured stable Agent name."""
        return self._name

    def run(self, task: Task, context: Context) -> Message:
        """Build one model request from the conversation and current Task."""
        messages: list[Message] = []
        if self._system_prompt is not None:
            messages.append(Message(role=MessageRole.SYSTEM, content=self._system_prompt))
        messages.extend(context.messages)
        messages.append(Message(role=MessageRole.USER, content=task.description))

        metadata = dict(self._request_metadata)
        metadata["execution_id"] = task.id
        response = self._provider.generate(
            ModelRequest(
                messages=tuple(messages),
                model=self._model,
                parameters=dict(self._parameters),
                metadata=metadata,
            )
        )
        return response.message
