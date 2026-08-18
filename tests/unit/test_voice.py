from __future__ import annotations

import asyncio

import pytest

from numa.agents import AsyncAgent, AsyncEchoAgent
from numa.core import (
    AgentExecutionError,
    Context,
    Message,
    SpeechRecognitionError,
    SpeechSynthesisError,
    Task,
    TaskStatus,
)
from numa.events import EventBus, EventType, InMemoryEventHandler
from numa.runtime import AsyncAgentRuntime
from numa.voice import (
    EchoSpeechRecognizer,
    EchoSpeechSynthesizer,
    SpeechRecognizer,
    SpeechSynthesizer,
    SynthesizedAudio,
    Transcript,
    VoiceSession,
)


class FailingRecognizer(SpeechRecognizer):
    @property
    def name(self) -> str:
        return "failing_recognizer"

    async def transcribe(self, audio: bytes) -> Transcript:
        del audio
        raise RuntimeError("recognizer unavailable")


class EmptyRecognizer(SpeechRecognizer):
    @property
    def name(self) -> str:
        return "empty_recognizer"

    async def transcribe(self, audio: bytes) -> Transcript:
        del audio
        return Transcript(text="  ")


class LanguageRecognizer(SpeechRecognizer):
    @property
    def name(self) -> str:
        return "language_recognizer"

    async def transcribe(self, audio: bytes) -> Transcript:
        return Transcript(text=audio.decode(), language="zh-CN")


class FailingSynthesizer(SpeechSynthesizer):
    @property
    def name(self) -> str:
        return "failing_synthesizer"

    async def synthesize(self, text: str) -> SynthesizedAudio:
        del text
        raise RuntimeError("synthesizer unavailable")


class EmptySynthesizer(SpeechSynthesizer):
    @property
    def name(self) -> str:
        return "empty_synthesizer"

    async def synthesize(self, text: str) -> SynthesizedAudio:
        del text
        return SynthesizedAudio(data=b"")


class FailingAgent(AsyncAgent):
    @property
    def name(self) -> str:
        return "failing_agent"

    async def run(self, task: Task, context: Context) -> Message:
        del task, context
        raise ValueError("agent failed")


class WaitingAgent(AsyncAgent):
    def __init__(self, started: asyncio.Event) -> None:
        self.started = started

    @property
    def name(self) -> str:
        return "waiting_agent"

    async def run(self, task: Task, context: Context) -> Message:
        del task, context
        self.started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


def event_types(collector: InMemoryEventHandler) -> list[EventType]:
    return [event.type for event in collector.events]


def test_voice_session_runs_complete_correlated_turn() -> None:
    async def scenario() -> None:
        collector = InMemoryEventHandler()
        runtime = AsyncAgentRuntime(event_bus=EventBus([collector]))
        session = VoiceSession(
            LanguageRecognizer(),
            EchoSpeechSynthesizer(),
            runtime,
            AsyncEchoAgent(),
            session_id="session-123",
        )

        result = await session.handle_turn(
            "你好 Numa".encode(),
            task_metadata={"source": "push-to-talk"},
        )

        assert result.session_id == "session-123"
        assert result.transcript == Transcript(text="你好 Numa", language="zh-CN")
        assert result.response.content == "你好 Numa"
        assert result.audio.data.decode() == "你好 Numa"
        assert result.task.status is TaskStatus.COMPLETED
        assert result.task.id == collector.events[0].execution_id
        assert result.task.metadata == {
            "source": "push-to-talk",
            "voice_session_id": "session-123",
            "voice_turn_id": result.turn_id,
        }
        assert session.context.messages == [result.response]
        assert event_types(collector) == [
            EventType.VOICE_TURN_STARTED,
            EventType.SPEECH_RECOGNITION_STARTED,
            EventType.SPEECH_RECOGNITION_COMPLETED,
            EventType.AGENT_STARTED,
            EventType.AGENT_COMPLETED,
            EventType.SPEECH_SYNTHESIS_STARTED,
            EventType.SPEECH_SYNTHESIS_COMPLETED,
            EventType.VOICE_TURN_COMPLETED,
        ]
        assert {event.execution_id for event in collector.events} == {result.task.id}
        voice_events = [
            event
            for event in collector.events
            if event.type not in {EventType.AGENT_STARTED, EventType.AGENT_COMPLETED}
        ]
        assert all(event.metadata["session_id"] == "session-123" for event in voice_events)
        assert all(event.metadata["turn_id"] == result.turn_id for event in voice_events)

    asyncio.run(scenario())


def test_voice_session_reuses_context_across_turns() -> None:
    async def scenario() -> None:
        session = VoiceSession(
            EchoSpeechRecognizer(),
            EchoSpeechSynthesizer(),
            AsyncAgentRuntime(),
            AsyncEchoAgent(),
        )

        first = await session.handle_turn(b"first")
        second = await session.handle_turn(b"second")

        assert first.turn_id != second.turn_id
        assert [message.content for message in session.context.messages] == ["first", "second"]

    asyncio.run(scenario())


@pytest.mark.parametrize("recognizer", [FailingRecognizer(), EmptyRecognizer()])
def test_voice_session_classifies_recognition_failures(recognizer: SpeechRecognizer) -> None:
    async def scenario() -> None:
        collector = InMemoryEventHandler()
        session = VoiceSession(
            recognizer,
            EchoSpeechSynthesizer(),
            AsyncAgentRuntime(event_bus=EventBus([collector])),
            AsyncEchoAgent(),
        )

        with pytest.raises(SpeechRecognitionError) as error:
            await session.handle_turn(b"private audio")

        assert event_types(collector) == [
            EventType.VOICE_TURN_STARTED,
            EventType.SPEECH_RECOGNITION_STARTED,
            EventType.SPEECH_RECOGNITION_FAILED,
            EventType.VOICE_TURN_FAILED,
        ]
        assert collector.events[-1].metadata["error_type"] == "SpeechRecognitionError"
        if isinstance(recognizer, FailingRecognizer):
            assert isinstance(error.value.__cause__, RuntimeError)

    asyncio.run(scenario())


@pytest.mark.parametrize("synthesizer", [FailingSynthesizer(), EmptySynthesizer()])
def test_voice_session_classifies_synthesis_failures(synthesizer: SpeechSynthesizer) -> None:
    async def scenario() -> None:
        collector = InMemoryEventHandler()
        session = VoiceSession(
            EchoSpeechRecognizer(),
            synthesizer,
            AsyncAgentRuntime(event_bus=EventBus([collector])),
            AsyncEchoAgent(),
        )

        with pytest.raises(SpeechSynthesisError):
            await session.handle_turn(b"hello")

        assert event_types(collector)[-3:] == [
            EventType.SPEECH_SYNTHESIS_STARTED,
            EventType.SPEECH_SYNTHESIS_FAILED,
            EventType.VOICE_TURN_FAILED,
        ]
        assert EventType.AGENT_COMPLETED in event_types(collector)

    asyncio.run(scenario())


def test_voice_session_preserves_agent_failure() -> None:
    async def scenario() -> None:
        collector = InMemoryEventHandler()
        session = VoiceSession(
            EchoSpeechRecognizer(),
            EchoSpeechSynthesizer(),
            AsyncAgentRuntime(event_bus=EventBus([collector])),
            FailingAgent(),
        )

        with pytest.raises(AgentExecutionError):
            await session.handle_turn(b"hello")

        assert event_types(collector)[-2:] == [
            EventType.AGENT_FAILED,
            EventType.VOICE_TURN_FAILED,
        ]
        assert EventType.SPEECH_SYNTHESIS_STARTED not in event_types(collector)

    asyncio.run(scenario())


def test_voice_session_propagates_cancellation() -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        collector = InMemoryEventHandler()
        session = VoiceSession(
            EchoSpeechRecognizer(),
            EchoSpeechSynthesizer(),
            AsyncAgentRuntime(event_bus=EventBus([collector])),
            WaitingAgent(started),
        )
        execution = asyncio.create_task(session.handle_turn(b"cancel me"))
        await started.wait()

        execution.cancel()
        with pytest.raises(asyncio.CancelledError):
            await execution

        assert event_types(collector)[-2:] == [
            EventType.AGENT_CANCELLED,
            EventType.VOICE_TURN_CANCELLED,
        ]

    asyncio.run(scenario())


def test_voice_events_do_not_include_audio_transcript_or_response() -> None:
    async def scenario() -> None:
        collector = InMemoryEventHandler()
        session = VoiceSession(
            EchoSpeechRecognizer(),
            EchoSpeechSynthesizer(),
            AsyncAgentRuntime(event_bus=EventBus([collector])),
            AsyncEchoAgent(),
        )
        secret = "do not record this"

        await session.handle_turn(secret.encode())

        assert all(secret not in repr(event.metadata) for event in collector.events)
        assert all("audio" not in event.metadata for event in collector.events)
        assert all("transcript" not in event.metadata for event in collector.events)
        assert all("response" not in event.metadata for event in collector.events)

    asyncio.run(scenario())


def test_echo_recognizer_rejects_non_utf8_fixture_input() -> None:
    async def scenario() -> None:
        with pytest.raises(SpeechRecognitionError, match="UTF-8"):
            await EchoSpeechRecognizer().transcribe(b"\xff")

    asyncio.run(scenario())
