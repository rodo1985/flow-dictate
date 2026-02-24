"""Command-line entrypoint for flow-dictate."""

from __future__ import annotations

import argparse
from typing import Sequence

from flow_dictate.audio import StubAudioCapture
from flow_dictate.config import AppConfig
from flow_dictate.hotkey import StubHotkeyCapture
from flow_dictate.injector import StdoutTextInjector
from flow_dictate.service import DictationService
from flow_dictate.transcription import StubOpenAITranscriptionClient


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
    return parser


def build_default_service(config: AppConfig, simulate_trigger: bool = False) -> DictationService:
    """Create a default orchestrator wired with local stub implementations.

    Parameters:
        config: Runtime configuration values for the service.
        simulate_trigger: Whether the first hotkey wait auto-triggers.

    Returns:
        DictationService: Service wired with in-process stubs.

    Raises:
        None.

    Example:
        ``service = build_default_service(AppConfig(), simulate_trigger=True)``
    """

    return DictationService(
        config=config,
        hotkey_capture=StubHotkeyCapture(auto_trigger_once=simulate_trigger),
        audio_capture=StubAudioCapture(
            sample_rate_hz=config.sample_rate_hz,
            channels=config.channels,
        ),
        transcription_client=StubOpenAITranscriptionClient(),
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

    Example:
        ``main(["--run-once", "--simulate-trigger"])``
    """

    parser = build_parser()
    args = parser.parse_args(argv)

    config = AppConfig.from_env()
    service = build_default_service(config=config, simulate_trigger=args.simulate_trigger)

    if args.run_once:
        service.run_once(timeout_seconds=0.0)
        return 0

    # In scaffold mode this loop uses stub components and is safe for dry runs.
    service.run_forever(max_iterations=args.max_iterations)
    return 0
