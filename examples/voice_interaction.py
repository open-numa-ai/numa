"""Run a provider-neutral push-to-talk style voice turn offline."""

import asyncio

from numa import (
    AsyncAgentRuntime,
    EchoSpeechRecognizer,
    EchoSpeechSynthesizer,
    EventBus,
    InMemoryEventHandler,
    VoiceSession,
)
from numa.agents import AsyncEchoAgent


async def main() -> None:
    events = InMemoryEventHandler()
    session = VoiceSession(
        EchoSpeechRecognizer(),
        EchoSpeechSynthesizer(),
        AsyncAgentRuntime(event_bus=EventBus([events])),
        AsyncEchoAgent(),
    )

    # Echo adapters treat UTF-8 bytes as a deterministic teaching fixture.
    # Application adapters can replace them with real ASR and TTS services.
    result = await session.handle_turn(b"Hello from a voice turn")

    print(result.transcript.text)
    print(result.response.content)
    print(result.audio.data.decode())
    print([event.type.value for event in events.events])


if __name__ == "__main__":
    asyncio.run(main())
