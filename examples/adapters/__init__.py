"""Optional provider adapters used by Numa integration examples."""

from examples.adapters.openai_speech import (
    OpenAIAudioClient,
    OpenAISpeechRecognizer,
    OpenAISpeechSynthesizer,
)

__all__ = [
    "OpenAIAudioClient",
    "OpenAISpeechRecognizer",
    "OpenAISpeechSynthesizer",
]
