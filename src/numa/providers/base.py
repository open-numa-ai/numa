"""Model provider contracts independent of vendor SDKs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from numa.core import Message


@dataclass(frozen=True, slots=True)
class ModelRequest:
    """A provider-neutral request for one model response."""

    messages: tuple[Message, ...]
    model: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModelUsage:
    """Optional token usage reported by a model provider."""

    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        """Return the total number of reported tokens."""
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class ModelResponse:
    """A provider-neutral model response."""

    message: Message
    model: str | None = None
    usage: ModelUsage | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelProvider(ABC):
    """Synchronous interface implemented by model provider adapters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the stable provider name."""

    @abstractmethod
    def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate one response for a provider-neutral request."""
