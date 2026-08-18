"""Provider-neutral data models for turn-based voice interaction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from numa.core import Message, Task


@dataclass(frozen=True, slots=True)
class Transcript:
    """Text recognized from one complete audio input."""

    text: str
    language: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SynthesizedAudio:
    """One complete synthesized audio response."""

    data: bytes
    media_type: str = "audio/wav"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VoiceTurnResult:
    """Correlated result of recognition, Agent execution, and synthesis."""

    session_id: str
    turn_id: str
    task: Task
    transcript: Transcript
    response: Message
    audio: SynthesizedAudio
