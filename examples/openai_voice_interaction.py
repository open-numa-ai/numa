"""Validate a recorded audio turn against OpenAI transcription and speech."""

from __future__ import annotations

import argparse
import asyncio
from importlib import import_module
from pathlib import Path
from typing import Any, cast

from examples.adapters.openai_speech import (
    OpenAIAudioClient,
    OpenAISpeechRecognizer,
    OpenAISpeechSynthesizer,
)
from numa import AsyncAgentRuntime, VoiceSession
from numa.agents import AsyncEchoAgent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transcribe an audio file, run a Numa Agent, and synthesize the response."
    )
    parser.add_argument("input", type=Path, help="Input audio file, for example input.wav")
    parser.add_argument("output", type=Path, help="Output WAV file")
    parser.add_argument("--language", help="Optional ISO-639-1 input language, for example en")
    parser.add_argument("--transcription-model", default="gpt-4o-transcribe")
    parser.add_argument("--speech-model", default="tts-1")
    parser.add_argument("--voice", default="alloy")
    return parser.parse_args()


def create_openai_client() -> OpenAIAudioClient:
    try:
        module = import_module("openai")
        factory: Any = module.AsyncOpenAI
    except (AttributeError, ImportError) as exc:
        raise RuntimeError(
            "Install the optional OpenAI SDK with `uv run --with openai ...`"
        ) from exc
    return cast(OpenAIAudioClient, factory())


async def run(args: argparse.Namespace) -> None:
    if args.input.suffix.lower() != ".wav":
        raise ValueError("This validation example currently expects a WAV input file")
    if args.output.suffix.lower() != ".wav":
        raise ValueError("The output path must use the .wav extension")

    input_audio = args.input.read_bytes()
    client = create_openai_client()
    session = VoiceSession(
        OpenAISpeechRecognizer(
            client,
            model=args.transcription_model,
            filename=args.input.name,
            media_type="audio/wav",
            language=args.language,
        ),
        OpenAISpeechSynthesizer(
            client,
            model=args.speech_model,
            voice=args.voice,
            response_format="wav",
        ),
        AsyncAgentRuntime(),
        AsyncEchoAgent(),
    )

    result = await session.handle_turn(input_audio)
    args.output.write_bytes(result.audio.data)
    print(f"transcript={result.transcript.text}")
    print(f"response={result.response.content}")
    print(f"audio={args.output}")


def main() -> None:
    asyncio.run(run(parse_args()))


if __name__ == "__main__":
    main()
