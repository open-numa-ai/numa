"""Deterministic speech adapters for tests and examples."""

from numa.core import SpeechRecognitionError
from numa.voice.base import SpeechRecognizer, SpeechSynthesizer
from numa.voice.models import SynthesizedAudio, Transcript


class EchoSpeechRecognizer(SpeechRecognizer):
    """Decode UTF-8 bytes as a transcript without processing real audio."""

    @property
    def name(self) -> str:
        return "echo_speech_recognizer"

    async def transcribe(self, audio: bytes) -> Transcript:
        try:
            text = audio.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SpeechRecognitionError("Echo audio must contain UTF-8 text") from exc
        return Transcript(text=text)


class EchoSpeechSynthesizer(SpeechSynthesizer):
    """Encode response text as UTF-8 bytes without producing real audio."""

    @property
    def name(self) -> str:
        return "echo_speech_synthesizer"

    async def synthesize(self, text: str) -> SynthesizedAudio:
        return SynthesizedAudio(data=text.encode("utf-8"), media_type="text/plain; charset=utf-8")
