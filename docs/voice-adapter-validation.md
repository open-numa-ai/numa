# Voice Adapter Validation

The OpenAI reference adapter validates Numa's provider-neutral voice contracts
against real transcription and speech endpoints without adding an SDK to the
core package dependencies.

The adapter lives in `examples/adapters/openai_speech.py`. It accepts an
injected `AsyncOpenAI`-compatible client and translates provider failures into
Numa's `SpeechRecognitionError` and `SpeechSynthesisError` boundaries.

## What the Validation Covers

```text
WAV file
    -> OpenAI transcription endpoint
    -> Transcript
    -> VoiceSession
    -> AsyncAgentRuntime + AsyncEchoAgent
    -> OpenAI speech endpoint
    -> WAV file
```

The default models are `gpt-4o-transcribe` for transcription and `tts-1` for
speech generation. The OpenAI transcription API accepts an extension-bearing
audio file and the speech API supports WAV output:

- [Create transcription](https://developers.openai.com/api/reference/python/resources/audio/subresources/transcriptions/methods/create)
- [Create speech](https://developers.openai.com/api/reference/python/resources/audio/subresources/speech/methods/create)

## Run the Credentialed Smoke Test

Prepare a mono WAV recording. On Linux with ALSA, one possible command is:

```bash
arecord -d 5 -f S16_LE -r 16000 -c 1 /tmp/numa-input.wav
```

Set an API key in the environment and run the optional SDK without adding it to
the project dependencies:

```bash
export OPENAI_API_KEY="..."
uv run --with openai python examples/openai_voice_interaction.py \
  /tmp/numa-input.wav /tmp/numa-output.wav --language zh
```

The example prints the recognized transcript, the Agent response, and the
output path. `AsyncEchoAgent` intentionally returns the transcript unchanged;
this isolates speech adapter validation from LLM prompting and model-provider
behavior.

The command sends the input recording and Agent response to an external
service and may incur API usage charges. Do not use sensitive recordings unless
the application's data-handling policy permits it.

## Adapter Configuration

Applications can inject the adapters into a normal `VoiceSession`:

```python
from openai import AsyncOpenAI

from examples.adapters.openai_speech import (
    OpenAISpeechRecognizer,
    OpenAISpeechSynthesizer,
)
from numa import AsyncAgentRuntime, VoiceSession
from numa.agents import AsyncEchoAgent

client = AsyncOpenAI()
session = VoiceSession(
    OpenAISpeechRecognizer(
        client,
        model="gpt-4o-transcribe",
        filename="input.wav",
        media_type="audio/wav",
        language="en",
    ),
    OpenAISpeechSynthesizer(
        client,
        model="tts-1",
        voice="alloy",
        response_format="wav",
    ),
    AsyncAgentRuntime(),
    AsyncEchoAgent(),
)
```

The recognizer sends a `(filename, bytes, media_type)` file tuple so the
provider can identify the audio format. The synthesizer validates that the
binary response is non-empty and maps the selected response format to a media
type.

## Validation Boundaries

Offline tests verify request construction, response translation, exception
chaining, configuration validation, and a complete `VoiceSession` turn with a
fake client. They do not prove service availability, account access, transcript
accuracy, voice quality, latency, or microphone compatibility.

A successful credentialed smoke test proves endpoint transport and Numa
composition for one recorded turn. It does not validate streaming, partial
transcripts, interruption, playback, or closed-loop conversational quality.
