"""Turn-based voice composition above the asynchronous Runtime."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from numa.agents import AsyncAgent
from numa.core import (
    Context,
    Message,
    MessageRole,
    SpeechRecognitionError,
    SpeechSynthesisError,
    Task,
)
from numa.events import Event, EventType
from numa.runtime import AsyncAgentRuntime
from numa.voice.base import SpeechRecognizer, SpeechSynthesizer
from numa.voice.models import SynthesizedAudio, Transcript, VoiceTurnResult


class VoiceSession:
    """Run complete audio turns through recognition, Runtime, and synthesis.

    A session serializes turns so its shared ``Context`` remains ordered. The
    injected Runtime continues to own Agent lifecycle, persistence, middleware,
    permissions, resilience, and Agent events.
    """

    def __init__(
        self,
        recognizer: SpeechRecognizer,
        synthesizer: SpeechSynthesizer,
        runtime: AsyncAgentRuntime,
        agent: AsyncAgent,
        *,
        context: Context | None = None,
        session_id: str | None = None,
    ) -> None:
        self.recognizer = recognizer
        self.synthesizer = synthesizer
        self.runtime = runtime
        self.agent = agent
        self.context = context if context is not None else Context()
        self.session_id = session_id or str(uuid4())
        self._turn_lock = asyncio.Lock()

    async def handle_turn(
        self,
        audio: bytes,
        *,
        task_metadata: dict[str, Any] | None = None,
    ) -> VoiceTurnResult:
        """Process one complete audio input and return its correlated result."""
        async with self._turn_lock:
            turn_id = str(uuid4())
            task_id = str(uuid4())
            event_metadata = {"session_id": self.session_id, "turn_id": turn_id}
            self._emit(
                EventType.VOICE_TURN_STARTED,
                task_id,
                "voice_session",
                event_metadata,
            )

            try:
                transcript = await self._transcribe(audio, task_id, event_metadata)
                metadata = dict(task_metadata or {})
                metadata.update(
                    {
                        "voice_session_id": self.session_id,
                        "voice_turn_id": turn_id,
                    }
                )
                task = Task(description=transcript.text, id=task_id, metadata=metadata)
                response = await self.runtime.run(
                    self.agent,
                    task,
                    self.context,
                    input_message=Message(
                        role=MessageRole.USER,
                        content=transcript.text,
                    ),
                )
                synthesized_audio = await self._synthesize(
                    response.content,
                    task_id,
                    event_metadata,
                )
            except asyncio.CancelledError:
                self._emit(
                    EventType.VOICE_TURN_CANCELLED,
                    task_id,
                    "voice_session",
                    event_metadata,
                )
                raise
            except Exception as exc:
                self._emit(
                    EventType.VOICE_TURN_FAILED,
                    task_id,
                    "voice_session",
                    {**event_metadata, "error_type": type(exc).__name__},
                )
                raise

            self._emit(
                EventType.VOICE_TURN_COMPLETED,
                task_id,
                "voice_session",
                event_metadata,
            )
            return VoiceTurnResult(
                session_id=self.session_id,
                turn_id=turn_id,
                task=task,
                transcript=transcript,
                response=response,
                audio=synthesized_audio,
            )

    async def _transcribe(
        self,
        audio: bytes,
        task_id: str,
        event_metadata: dict[str, str],
    ) -> Transcript:
        self._emit(
            EventType.SPEECH_RECOGNITION_STARTED,
            task_id,
            self.recognizer.name,
            event_metadata,
        )
        try:
            transcript = await self.recognizer.transcribe(audio)
            if not transcript.text.strip():
                raise SpeechRecognitionError("Speech recognizer returned an empty transcript")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            error = (
                exc
                if isinstance(exc, SpeechRecognitionError)
                else SpeechRecognitionError(f"Speech recognizer {self.recognizer.name!r} failed")
            )
            self._emit(
                EventType.SPEECH_RECOGNITION_FAILED,
                task_id,
                self.recognizer.name,
                {**event_metadata, "error_type": type(error).__name__},
            )
            if error is exc:
                raise
            raise error from exc

        metadata = dict(event_metadata)
        if transcript.language is not None:
            metadata["language"] = transcript.language
        self._emit(
            EventType.SPEECH_RECOGNITION_COMPLETED,
            task_id,
            self.recognizer.name,
            metadata,
        )
        return transcript

    async def _synthesize(
        self,
        text: str,
        task_id: str,
        event_metadata: dict[str, str],
    ) -> SynthesizedAudio:
        self._emit(
            EventType.SPEECH_SYNTHESIS_STARTED,
            task_id,
            self.synthesizer.name,
            event_metadata,
        )
        try:
            audio = await self.synthesizer.synthesize(text)
            if not audio.data:
                raise SpeechSynthesisError("Speech synthesizer returned empty audio")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            error = (
                exc
                if isinstance(exc, SpeechSynthesisError)
                else SpeechSynthesisError(f"Speech synthesizer {self.synthesizer.name!r} failed")
            )
            self._emit(
                EventType.SPEECH_SYNTHESIS_FAILED,
                task_id,
                self.synthesizer.name,
                {**event_metadata, "error_type": type(error).__name__},
            )
            if error is exc:
                raise
            raise error from exc

        self._emit(
            EventType.SPEECH_SYNTHESIS_COMPLETED,
            task_id,
            self.synthesizer.name,
            {**event_metadata, "media_type": audio.media_type},
        )
        return audio

    def _emit(
        self,
        event_type: EventType,
        execution_id: str,
        component_name: str,
        metadata: dict[str, Any],
    ) -> None:
        self.runtime.event_bus.emit(
            Event(
                type=event_type,
                execution_id=execution_id,
                component_name=component_name,
                metadata=metadata,
            )
        )
