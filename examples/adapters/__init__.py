"""Optional provider adapters used by Numa integration examples."""

from examples.adapters.openai_speech import (
    OpenAIAudioClient,
    OpenAISpeechRecognizer,
    OpenAISpeechSynthesizer,
)
from examples.adapters.opentelemetry_spans import (
    OpenTelemetrySpanExporter,
    OpenTelemetryTracer,
    create_opentelemetry_exporter,
)

__all__ = [
    "OpenAIAudioClient",
    "OpenAISpeechRecognizer",
    "OpenAISpeechSynthesizer",
    "OpenTelemetrySpanExporter",
    "OpenTelemetryTracer",
    "create_opentelemetry_exporter",
]
