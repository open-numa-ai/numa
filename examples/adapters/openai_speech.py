"""Optional OpenAI speech adapters for credentialed integration validation.

This module intentionally does not import the OpenAI SDK. Applications inject
an ``AsyncOpenAI``-compatible client, keeping the SDK outside Numa's core
dependencies while retaining an executable reference integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from numa import (
    SpeechRecognitionError,
    SpeechRecognizer,
    SpeechSynthesisError,
    SpeechSynthesizer,
    SynthesizedAudio,
    Transcript,
)

_MEDIA_TYPES = {
    "aac": "audio/aac",
    "flac": "audio/flac",
    "mp3": "audio/mpeg",
    "opus": "audio/opus",
    "pcm": "audio/pcm",
    "wav": "audio/wav",
}


class _AsyncCreateResource(Protocol):
    async def create(self, **parameters: Any) -> Any:
        """Create one provider resource."""


class _OpenAIAudioResources(Protocol):
    @property
    def transcriptions(self) -> _AsyncCreateResource:
        """Return the asynchronous transcription resource."""

    @property
    def speech(self) -> _AsyncCreateResource:
        """Return the asynchronous speech resource."""


@runtime_checkable
class OpenAIAudioClient(Protocol):
    """Minimal structural boundary implemented by OpenAI ``AsyncOpenAI``."""

    @property
    def audio(self) -> _OpenAIAudioResources:
        """Return the client's audio resources."""


@dataclass(frozen=True, slots=True)
class OpenAISpeechRecognizer(SpeechRecognizer):
    """Transcribe complete audio through an injected OpenAI async client."""

    client: OpenAIAudioClient
    model: str = "gpt-4o-transcribe"
    filename: str = "input.wav"
    media_type: str = "audio/wav"
    language: str | None = None

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("model cannot be empty")
        if not self.filename.strip() or "." not in self.filename:
            raise ValueError("filename must include an audio extension")
        if not self.media_type.startswith("audio/"):
            raise ValueError("media_type must be an audio media type")
        if self.language is not None and not self.language.strip():
            raise ValueError("language cannot be empty")

    @property
    def name(self) -> str:
        return "openai_speech_recognizer"

    async def transcribe(self, audio: bytes) -> Transcript:
        if not audio:
            raise SpeechRecognitionError("OpenAI transcription input cannot be empty")

        parameters: dict[str, Any] = {
            "model": self.model,
            "file": (self.filename, audio, self.media_type),
            "response_format": "json",
        }
        if self.language is not None:
            parameters["language"] = self.language

        try:
            response = await self.client.audio.transcriptions.create(**parameters)
            text = response.text
        except Exception as exc:
            raise SpeechRecognitionError("OpenAI transcription request failed") from exc

        if not isinstance(text, str) or not text.strip():
            raise SpeechRecognitionError("OpenAI transcription returned empty text")
        return Transcript(
            text=text,
            language=self.language,
            metadata={"provider": "openai", "model": self.model},
        )


@dataclass(frozen=True, slots=True)
class OpenAISpeechSynthesizer(SpeechSynthesizer):
    """Synthesize complete audio through an injected OpenAI async client."""

    client: OpenAIAudioClient
    model: str = "tts-1"
    voice: str = "alloy"
    response_format: str = "wav"

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("model cannot be empty")
        if not self.voice.strip():
            raise ValueError("voice cannot be empty")
        if self.response_format not in _MEDIA_TYPES:
            supported = ", ".join(sorted(_MEDIA_TYPES))
            raise ValueError(f"response_format must be one of: {supported}")

    @property
    def name(self) -> str:
        return "openai_speech_synthesizer"

    async def synthesize(self, text: str) -> SynthesizedAudio:
        if not text.strip():
            raise SpeechSynthesisError("OpenAI speech input cannot be empty")

        try:
            response = await self.client.audio.speech.create(
                model=self.model,
                voice=self.voice,
                input=text,
                response_format=self.response_format,
            )
            content = response.content
        except Exception as exc:
            raise SpeechSynthesisError("OpenAI speech request failed") from exc

        if not isinstance(content, bytes) or not content:
            raise SpeechSynthesisError("OpenAI speech request returned empty audio")
        return SynthesizedAudio(
            data=content,
            media_type=_MEDIA_TYPES[self.response_format],
            metadata={
                "provider": "openai",
                "model": self.model,
                "voice": self.voice,
            },
        )
