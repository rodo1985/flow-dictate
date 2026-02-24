"""Command-line entrypoint for flow-dictate."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from flow_dictate.audio import StubAudioCapture
from flow_dictate.config import AppConfig
from flow_dictate.hotkey import MacOSGlobalHotkeyCapture, StubHotkeyCapture
from flow_dictate.injector import StdoutTextInjector
from flow_dictate.permissions import format_preflight_report, run_permission_preflight
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
        description="CLI for the macOS dictation daemon scaffold.",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser(
        "run",
        help="Start the dictation service loop.",
    )
    run_parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run a single orchestration cycle instead of a loop.",
    )
    run_parser.add_argument(
        "--simulate-trigger",
        action="store_true",
        help="Force the first hotkey wait to trigger in this stub scaffold.",
    )
    run_parser.add_argument(
        "--use-stub-hotkey",
        action="store_true",
        help="Force the stub hotkey listener instead of the real macOS global hotkey.",
    )
    run_parser.add_argument(
        "--max-iterations",
        type=_positive_int,
        default=None,
        help="Stop the loop after N iterations (useful for local dry runs).",
    )

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Run environment and permission preflight checks.",
    )
    doctor_parser.add_argument(
        "--prompt-permissions",
        action="store_true",
        help="Allow macOS permission prompts where supported.",
    )

    return parser


def build_default_service(
    config: AppConfig,
    simulate_trigger: bool = False,
    use_stub_hotkey: bool = False,
) -> DictationService:
    """Create a default orchestrator wired with local stub implementations.

    Parameters:
        config: Runtime configuration values for the service.
        simulate_trigger: Whether the first hotkey wait auto-triggers.
        use_stub_hotkey: Whether to force stub hotkey behavior.

    Returns:
        DictationService: Service wired with in-process stubs.

    Raises:
        None.

    Example:
        ``service = build_default_service(AppConfig(), simulate_trigger=True)``
    """

    if simulate_trigger or use_stub_hotkey:
        hotkey_capture = StubHotkeyCapture(auto_trigger_once=simulate_trigger)
    else:
        hotkey_capture = MacOSGlobalHotkeyCapture(hotkey=config.hotkey)

    return DictationService(
        config=config,
        hotkey_capture=hotkey_capture,
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

    if args.command == "doctor":
        report = run_permission_preflight(prompt=args.prompt_permissions)
        print(format_preflight_report(report))
        return 0 if report.all_required_granted else 1

    if args.command is None:
        parser.print_help()
        return 0

    config = AppConfig.from_env()
    try:
        service = build_default_service(
            config=config,
            simulate_trigger=args.simulate_trigger,
            use_stub_hotkey=args.use_stub_hotkey,
        )
    except RuntimeError as exc:
        print(
            "Unable to start real global hotkey listener. "
            "Run `flow-dictate doctor` and verify Input Monitoring permissions.\n"
            f"Details: {exc}",
            file=sys.stderr,
        )
        return 2

    if args.run_once:
        service.run_once(timeout_seconds=0.0)
        return 0

    service.run_forever(max_iterations=args.max_iterations)
    return 0
