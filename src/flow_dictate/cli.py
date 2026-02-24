"""Command-line entrypoint for flow-dictate."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from flow_dictate.audio import MicrophoneAudioCapture, StubAudioCapture
from flow_dictate.config import AppConfig
from flow_dictate.hotkey import StubHotkeyCapture
from flow_dictate.injector import StdoutTextInjector
from flow_dictate.service import DictationService
from flow_dictate.transcription import (
    OpenAIRealtimeTranscriptionClient,
    StubOpenAITranscriptionClient,
)


def _positive_int(value: str) -> int:
    """Parse a positive integer for argparse options.

    Parameters:
        value: Raw CLI argument value.

    Returns:
        int: Parsed positive integer.

    Raises:
        argparse.ArgumentTypeError: If value is not a positive integer.

    Example:
        ``_positive_int("5")``
    """

    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Expected an integer value.") from exc

    if parsed <= 0:
        raise argparse.ArgumentTypeError("Expected a value greater than 0.")

    return parsed


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the flow-dictate CLI.

    Parameters:
        None.

    Returns:
        argparse.ArgumentParser: Configured parser.

    Raises:
        None.

    Example:
        ``parser = build_parser()``
    """

    parser = argparse.ArgumentParser(
        prog="flow-dictate",
        description="Scaffold CLI for a macOS dictation daemon.",
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run a single orchestration cycle instead of a loop.",
    )
    parser.add_argument(
        "--simulate-trigger",
        action="store_true",
        help="Force the first hotkey wait to trigger in this stub scaffold.",
    )
    parser.add_argument(
        "--max-iterations",
        type=_positive_int,
        default=None,
        help="Stop the loop after N iterations (useful for local dry runs).",
    )
    parser.add_argument(
        "--backend",
        choices=["stub", "realtime"],
        default="stub",
        help=(
            "Choose the runtime backend. "
            "'stub' is offline and deterministic; "
            "'realtime' uses microphone capture + OpenAI Realtime transcription."
        ),
    )
    return parser


def build_default_service(
    config: AppConfig,
    simulate_trigger: bool = False,
    backend: str = "stub",
) -> DictationService:
    """Create a default orchestrator wired with either stub or realtime backends.

    Parameters:
        config: Runtime configuration values for the service.
        simulate_trigger: Whether the first hotkey wait auto-triggers.
        backend: Runtime backend identifier (``stub`` or ``realtime``).

    Returns:
        DictationService: Service wired with selected backend components.

    Raises:
        ValueError: If backend is unknown.

    Example:
        ``service = build_default_service(AppConfig(), simulate_trigger=True, backend="stub")``
    """

    if backend not in {"stub", "realtime"}:
        raise ValueError(f"Unsupported backend: {backend}")

    if backend == "realtime":
        audio_capture = MicrophoneAudioCapture(
            sample_rate_hz=config.sample_rate_hz,
            channels=config.channels,
            device=config.audio_input_device,
        )
        transcription_client = OpenAIRealtimeTranscriptionClient.from_config(config=config)
    else:
        audio_capture = StubAudioCapture(
            sample_rate_hz=config.sample_rate_hz,
            channels=config.channels,
        )
        transcription_client = StubOpenAITranscriptionClient()

    return DictationService(
        config=config,
        hotkey_capture=StubHotkeyCapture(auto_trigger_once=simulate_trigger),
        audio_capture=audio_capture,
        transcription_client=transcription_client,
        text_injector=StdoutTextInjector(),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the flow-dictate CLI.

    Parameters:
        argv: Optional argument list; defaults to ``sys.argv`` when omitted.

    Returns:
        int: Process-style exit code.

    Raises:
        ValueError: If configuration values from environment are invalid.
        RuntimeError: If backend initialization fails.

    Example:
        ``main(["--run-once", "--simulate-trigger"])``
    """

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = AppConfig.from_env()
        service = build_default_service(
            config=config,
            simulate_trigger=args.simulate_trigger,
            backend=args.backend,
        )
    except (ValueError, RuntimeError) as exc:
        print(f"flow-dictate startup error: {exc}", file=sys.stderr)
        return 2

    if args.run_once:
        service.run_once(timeout_seconds=0.0)
        return 0

    # In scaffold mode this loop uses stub components and is safe for dry runs.
    service.run_forever(max_iterations=args.max_iterations)
    return 0
