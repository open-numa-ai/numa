from __future__ import annotations

import asyncio

import pytest

from numa.agents import AsyncAgent, AsyncEchoAgent
from numa.core import (
    AgentExecutionError,
    Context,
    Message,
    MessageRole,
    SpeechRecognitionError,
    SpeechSynthesisError,
    Task,
    TaskStatus,
)
from numa.events import EventBus, EventType, InMemoryEventHandler
from numa.runtime import AsyncAgentRuntime
from numa.tasks import InMemoryTaskStore
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


class WaitingSynthesizer(SpeechSynthesizer):
    def __init__(self, started: asyncio.Event) -> None:
        self.started = started

    @property
    def name(self) -> str:
        return "waiting_synthesizer"

    async def synthesize(self, text: str) -> SynthesizedAudio:
        del text
        self.started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


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


class HistoryAwareAgent(AsyncAgent):
    def __init__(self) -> None:
        self.history: list[list[tuple[MessageRole, str]]] = []

    @property
    def name(self) -> str:
        return "history_aware"

    async def run(self, task: Task, context: Context) -> Message:
        self.history.append([(message.role, message.content) for message in context.messages])
        return Message(role=MessageRole.ASSISTANT, content=f"answer: {task.description}")


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
        assert [(message.role, message.content) for message in session.context.messages] == [
            (MessageRole.USER, "你好 Numa"),
            (MessageRole.ASSISTANT, "你好 Numa"),
        ]
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
        store = InMemoryTaskStore()
        agent = HistoryAwareAgent()
        session = VoiceSession(
            EchoSpeechRecognizer(),
            EchoSpeechSynthesizer(),
            AsyncAgentRuntime(task_store=store),
            agent,
        )

        first = await session.handle_turn(b"first")
        second = await session.handle_turn(b"second")

        assert first.turn_id != second.turn_id
        assert agent.history == [
            [],
            [
                (MessageRole.USER, "first"),
                (MessageRole.ASSISTANT, "answer: first"),
            ],
        ]
        expected_history = [
            (MessageRole.USER, "first"),
            (MessageRole.ASSISTANT, "answer: first"),
            (MessageRole.USER, "second"),
            (MessageRole.ASSISTANT, "answer: second"),
        ]
        assert [
            (message.role, message.content) for message in session.context.messages
        ] == expected_history
        first_record = store.load(first.task.id)
        second_record = store.load(second.task.id)
        assert first_record is not None
        assert second_record is not None
        assert [
            (message.role, message.content) for message in first_record.context.messages
        ] == expected_history[:2]
        assert [
            (message.role, message.content) for message in second_record.context.messages
        ] == expected_history

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
        assert [(message.role, message.content) for message in session.context.messages] == [
            (MessageRole.USER, "hello"),
            (MessageRole.ASSISTANT, "hello"),
        ]

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
        assert session.context.messages == []

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
        assert session.context.messages == []

    asyncio.run(scenario())


def test_voice_session_keeps_completed_text_turn_when_synthesis_is_cancelled() -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        collector = InMemoryEventHandler()
        session = VoiceSession(
            EchoSpeechRecognizer(),
            WaitingSynthesizer(started),
            AsyncAgentRuntime(event_bus=EventBus([collector])),
            AsyncEchoAgent(),
        )
        execution = asyncio.create_task(session.handle_turn(b"keep this turn"))
        await started.wait()

        execution.cancel()
        with pytest.raises(asyncio.CancelledError):
            await execution

        assert event_types(collector)[-2:] == [
            EventType.SPEECH_SYNTHESIS_STARTED,
            EventType.VOICE_TURN_CANCELLED,
        ]
        assert [(message.role, message.content) for message in session.context.messages] == [
            (MessageRole.USER, "keep this turn"),
            (MessageRole.ASSISTANT, "keep this turn"),
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
