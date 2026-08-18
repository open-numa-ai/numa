from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

import pytest

from numa import (
    AsyncAgentRuntime,
    SpeechRecognitionError,
    SpeechSynthesisError,
    VoiceSession,
)
from numa.agents import AsyncEchoAgent

_OPENAI_SPEECH_SPEC = spec_from_file_location(
    "tests.examples.adapters.openai_speech",
    Path(__file__).resolve().parents[2] / "examples" / "adapters" / "openai_speech.py",
)
assert _OPENAI_SPEECH_SPEC is not None
assert _OPENAI_SPEECH_SPEC.loader is not None
_OPENAI_SPEECH_MODULE = module_from_spec(_OPENAI_SPEECH_SPEC)
sys.modules[_OPENAI_SPEECH_SPEC.name] = _OPENAI_SPEECH_MODULE
_OPENAI_SPEECH_SPEC.loader.exec_module(_OPENAI_SPEECH_MODULE)
OpenAISpeechRecognizer = _OPENAI_SPEECH_MODULE.OpenAISpeechRecognizer
OpenAISpeechSynthesizer = _OPENAI_SPEECH_MODULE.OpenAISpeechSynthesizer


@dataclass
class FakeTranscriptionResponse:
    text: object


@dataclass
class FakeSpeechResponse:
    content: object


class FakeCreateResource:
    def __init__(self, response: object = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def create(self, **parameters: Any) -> Any:
        self.calls.append(parameters)
        if self.error is not None:
            raise self.error
        return self.response


class FakeAudioResources:
    def __init__(
        self,
        transcription: FakeCreateResource,
        speech: FakeCreateResource,
    ) -> None:
        self.transcriptions = transcription
        self.speech = speech


class FakeOpenAIClient:
    def __init__(
        self,
        transcription: FakeCreateResource,
        speech: FakeCreateResource,
    ) -> None:
        self.audio = FakeAudioResources(transcription, speech)


def make_client(
    *,
    transcript: object = "hello",
    audio: object = b"wave",
) -> tuple[FakeOpenAIClient, FakeCreateResource, FakeCreateResource]:
    transcriptions = FakeCreateResource(FakeTranscriptionResponse(transcript))
    speech = FakeCreateResource(FakeSpeechResponse(audio))
    return FakeOpenAIClient(transcriptions, speech), transcriptions, speech


def test_openai_recognizer_sends_extension_bearing_audio_file() -> None:
    async def scenario() -> None:
        client, transcriptions, _ = make_client(transcript="hello Numa")
        recognizer = OpenAISpeechRecognizer(
            client,
            model="gpt-4o-transcribe",
            filename="recording.wav",
            media_type="audio/wav",
            language="en",
        )

        result = await recognizer.transcribe(b"real wav bytes")

        assert result.text == "hello Numa"
        assert result.language == "en"
        assert result.metadata == {"provider": "openai", "model": "gpt-4o-transcribe"}
        assert transcriptions.calls == [
            {
                "model": "gpt-4o-transcribe",
                "file": ("recording.wav", b"real wav bytes", "audio/wav"),
                "response_format": "json",
                "language": "en",
            }
        ]

    asyncio.run(scenario())


def test_openai_recognizer_omits_unspecified_language() -> None:
    async def scenario() -> None:
        client, transcriptions, _ = make_client()

        await OpenAISpeechRecognizer(client).transcribe(b"wav")

        assert "language" not in transcriptions.calls[0]

    asyncio.run(scenario())


def test_openai_synthesizer_returns_declared_audio_format() -> None:
    async def scenario() -> None:
        client, _, speech = make_client(audio=b"generated wav")
        synthesizer = OpenAISpeechSynthesizer(
            client,
            model="tts-1",
            voice="alloy",
            response_format="wav",
        )

        result = await synthesizer.synthesize("hello Numa")

        assert result.data == b"generated wav"
        assert result.media_type == "audio/wav"
        assert result.metadata == {
            "provider": "openai",
            "model": "tts-1",
            "voice": "alloy",
        }
        assert speech.calls == [
            {
                "model": "tts-1",
                "voice": "alloy",
                "input": "hello Numa",
                "response_format": "wav",
            }
        ]

    asyncio.run(scenario())


def test_openai_adapters_complete_voice_session() -> None:
    async def scenario() -> None:
        client, transcriptions, speech = make_client(
            transcript="validated transcript",
            audio=b"validated response audio",
        )
        session = VoiceSession(
            OpenAISpeechRecognizer(client),
            OpenAISpeechSynthesizer(client),
            AsyncAgentRuntime(),
            AsyncEchoAgent(),
        )

        result = await session.handle_turn(b"wav input")

        assert result.transcript.text == "validated transcript"
        assert result.response.content == "validated transcript"
        assert result.audio.data == b"validated response audio"
        assert len(transcriptions.calls) == 1
        assert len(speech.calls) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("transcript", ["", "   ", None, 123])
def test_openai_recognizer_rejects_invalid_transcript(transcript: object) -> None:
    async def scenario() -> None:
        client, _, _ = make_client(transcript=transcript)

        with pytest.raises(SpeechRecognitionError, match="empty text"):
            await OpenAISpeechRecognizer(client).transcribe(b"wav")

    asyncio.run(scenario())


@pytest.mark.parametrize("audio", [b"", None, "not bytes"])
def test_openai_synthesizer_rejects_invalid_audio(audio: object) -> None:
    async def scenario() -> None:
        client, _, _ = make_client(audio=audio)

        with pytest.raises(SpeechSynthesisError, match="empty audio"):
            await OpenAISpeechSynthesizer(client).synthesize("hello")

    asyncio.run(scenario())


def test_openai_adapters_translate_provider_failures() -> None:
    async def scenario() -> None:
        transcription_error = RuntimeError("transcription transport failed")
        speech_error = RuntimeError("speech transport failed")
        client = FakeOpenAIClient(
            FakeCreateResource(error=transcription_error),
            FakeCreateResource(error=speech_error),
        )

        with pytest.raises(SpeechRecognitionError) as recognition:
            await OpenAISpeechRecognizer(client).transcribe(b"wav")
        with pytest.raises(SpeechSynthesisError) as synthesis:
            await OpenAISpeechSynthesizer(client).synthesize("hello")

        assert recognition.value.__cause__ is transcription_error
        assert synthesis.value.__cause__ is speech_error

    asyncio.run(scenario())


def test_openai_adapters_validate_configuration_and_empty_inputs() -> None:
    client, _, _ = make_client()

    with pytest.raises(ValueError, match="extension"):
        OpenAISpeechRecognizer(client, filename="recording")
    with pytest.raises(ValueError, match="audio media type"):
        OpenAISpeechRecognizer(client, media_type="application/octet-stream")
    with pytest.raises(ValueError, match="response_format"):
        OpenAISpeechSynthesizer(client, response_format="unknown")

    async def scenario() -> None:
        with pytest.raises(SpeechRecognitionError, match="cannot be empty"):
            await OpenAISpeechRecognizer(client).transcribe(b"")
        with pytest.raises(SpeechSynthesisError, match="cannot be empty"):
            await OpenAISpeechSynthesizer(client).synthesize(" ")

    asyncio.run(scenario())
