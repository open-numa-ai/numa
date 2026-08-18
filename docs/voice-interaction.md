# Voice Interaction

Numa provides a provider-neutral boundary for one complete, turn-based voice
interaction:

```text
complete audio input
    -> SpeechRecognizer
    -> transcript
    -> AsyncAgentRuntime
    -> Agent response
    -> SpeechSynthesizer
    -> complete audio output
```

The feature is intended for push-to-talk applications and integration tests.
It does not capture microphone input, play audio, select a speech vendor, or
implement streaming, voice activity detection, wake words, and full-duplex
conversation.

## Run a Voice Turn

```python
import asyncio

from numa import (
    AsyncAgentRuntime,
    EchoSpeechRecognizer,
    EchoSpeechSynthesizer,
    VoiceSession,
)
from numa.agents import AsyncEchoAgent


async def main() -> None:
    session = VoiceSession(
        EchoSpeechRecognizer(),
        EchoSpeechSynthesizer(),
        AsyncAgentRuntime(),
        AsyncEchoAgent(),
    )
    result = await session.handle_turn(b"Hello, Numa")
    print(result.transcript.text)
    print(result.response.content)
    print(result.audio.data)


asyncio.run(main())
```

The Echo adapters use UTF-8 bytes instead of real audio. They are deterministic
fixtures for examples and tests, not speech implementations.

For a credentialed file-to-file integration using optional OpenAI speech
endpoints, see [Voice Adapter Validation](voice-adapter-validation.md).

## Implement Adapters

Applications implement `SpeechRecognizer` and `SpeechSynthesizer` around their
chosen local or hosted speech SDKs:

```python
from numa import SpeechRecognizer, SpeechSynthesizer, SynthesizedAudio, Transcript


class ApplicationRecognizer(SpeechRecognizer):
    @property
    def name(self) -> str:
        return "application_recognizer"

    async def transcribe(self, audio: bytes) -> Transcript:
        text = await application_asr(audio)
        return Transcript(text=text, language="en")


class ApplicationSynthesizer(SpeechSynthesizer):
    @property
    def name(self) -> str:
        return "application_synthesizer"

    async def synthesize(self, text: str) -> SynthesizedAudio:
        data = await application_tts(text)
        return SynthesizedAudio(data=data, media_type="audio/mpeg")
```

Keep credentials, SDK clients, audio format conversion, rate limiting, and
vendor exception translation inside the adapters or application composition
root.

## Session and Runtime Semantics

`VoiceSession` owns one shared `Context` and serializes calls to `handle_turn`
so completed Agent messages stay ordered. Each turn receives a unique
`turn_id` and a Runtime `Task`; its task ID correlates voice, speech, and Agent
events. Reserved `voice_session_id` and `voice_turn_id` values are added to
task metadata.

The injected `AsyncAgentRuntime` still owns Agent lifecycle, middleware,
resilience, task persistence, tool registration, and tool permission policy.
Recognition failures raise `SpeechRecognitionError`, synthesis failures raise
`SpeechSynthesisError`, and Agent failures retain the Runtime's existing error
semantics. Cancellation remains visible to the caller.

## Events and Privacy

A successful turn emits:

```text
voice_turn.started
speech_recognition.started
speech_recognition.completed
agent.started
agent.completed
speech_synthesis.started
speech_synthesis.completed
voice_turn.completed
```

Failures emit a stage-specific failed event followed by `voice_turn.failed`.
Cancellation emits `voice_turn.cancelled`; cancellation during Agent execution
also retains the Runtime's `agent.cancelled` event.

Built-in events never contain audio bytes, transcripts, Agent responses, task
descriptions, or tool arguments. `session_id` and `turn_id` are included for
correlation, so applications that provide their own session ID should keep it
opaque and non-sensitive.

## Current Boundaries

Recognition and synthesis each consume and return one complete value. Streaming
audio frames, partial transcripts, model token streaming, incremental speech,
barge-in, device management, and playback are application concerns until real
integrations establish stable requirements for additional framework contracts.
