"""Speech recognition and synthesis extension points."""

from abc import ABC, abstractmethod

from numa.voice.models import SynthesizedAudio, Transcript


class SpeechRecognizer(ABC):
    """Convert one complete audio input into text."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the stable name used in lifecycle events."""

    @abstractmethod
    async def transcribe(self, audio: bytes) -> Transcript:
        """Recognize one complete audio input."""


class SpeechSynthesizer(ABC):
    """Convert one complete text response into audio."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the stable name used in lifecycle events."""

    @abstractmethod
    async def synthesize(self, text: str) -> SynthesizedAudio:
        """Synthesize one complete text response."""
