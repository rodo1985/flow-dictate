"""Command-line entrypoint for flow-dictate."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from flow_dictate.audio import MicrophoneAudioCapture, StubAudioCapture
from flow_dictate.config import AppConfig, VALID_BACKENDS, VALID_OUTPUT_MODES
from flow_dictate.hotkey import MacOSGlobalHotkeyCapture, StubHotkeyCapture
from flow_dictate.injector import (
    ClipboardTextInjector,
    MacOSActiveAppTextInjector,
    StdoutTextInjector,
)
from flow_dictate.interfaces import AudioCapture, TextInjector, TranscriptionClient
from flow_dictate.permissions import format_preflight_report, run_permission_preflight
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
        help="Force the first hotkey wait to trigger in dry-run mode.",
    )
    run_parser.add_argument(
        "--use-stub-hotkey",
        action="store_true",
        help="Force the stub hotkey listener instead of global macOS capture.",
    )
    run_parser.add_argument(
        "--max-iterations",
        type=_positive_int,
        default=None,
        help="Stop the loop after N iterations (useful for local dry runs).",
    )
    run_parser.add_argument(
        "--backend",
        choices=VALID_BACKENDS,
        default=None,
        help=(
            "Backend override. "
            "Defaults to FLOW_DICTATE_BACKEND or 'stub'."
        ),
    )
    run_parser.add_argument(
        "--output",
        choices=VALID_OUTPUT_MODES,
        default=None,
        help=(
            "Output destination override. "
            "Defaults to FLOW_DICTATE_OUTPUT_MODE or 'stdout'."
        ),
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


def _build_text_injector(config: AppConfig, output_mode: str) -> TextInjector:
    """Build a text injector implementation from the requested output mode.

    Parameters:
        config: Runtime configuration used for behavior toggles.
        output_mode: Destination mode for transcript output.

    Returns:
        TextInjector: Concrete injector implementation for the selected mode.

    Raises:
        ValueError: If an unsupported output mode is requested.

    Example:
        ``injector = _build_text_injector(config, output_mode="clipboard")``
    """

    if output_mode == "stdout":
        return StdoutTextInjector()

    if output_mode == "clipboard":
        return ClipboardTextInjector()

    if output_mode == "active-app":
        return MacOSActiveAppTextInjector(
            fallback_to_clipboard=config.active_app_fallback_to_clipboard
        )

    valid_modes = ", ".join(VALID_OUTPUT_MODES)
    raise ValueError(f"Unsupported output mode: {output_mode}. Valid modes: {valid_modes}.")


def _build_audio_and_transcription(
    config: AppConfig,
    backend: str,
) -> tuple[AudioCapture, TranscriptionClient]:
    """Build audio and transcription backends for the selected runtime mode.

    Parameters:
        config: Runtime configuration object.
        backend: Backend mode (``stub`` or ``realtime``).

    Returns:
        tuple[AudioCapture, TranscriptionClient]: Configured backend pair.

    Raises:
        ValueError: If backend is unsupported.
        RuntimeError: If realtime dependencies are unavailable.

    Example:
        ``audio, transcriber = _build_audio_and_transcription(config, backend="stub")``
    """

    if backend == "stub":
        return (
            StubAudioCapture(
                sample_rate_hz=config.sample_rate_hz,
                channels=config.channels,
            ),
            StubOpenAITranscriptionClient(),
        )

    if backend == "realtime":
        return (
            MicrophoneAudioCapture(
                sample_rate_hz=config.sample_rate_hz,
                channels=config.channels,
                device=config.audio_input_device,
            ),
            OpenAIRealtimeTranscriptionClient.from_config(config=config),
        )

    valid_backends = ", ".join(VALID_BACKENDS)
    raise ValueError(f"Unsupported backend: {backend}. Valid backends: {valid_backends}.")


def build_default_service(
    config: AppConfig,
    simulate_trigger: bool = False,
    use_stub_hotkey: bool = False,
    backend: str | None = None,
    output_mode: str | None = None,
) -> DictationService:
    """Create a default orchestrator using configured runtime implementations.

    Parameters:
        config: Runtime configuration values for the service.
        simulate_trigger: Whether the first hotkey wait auto-triggers.
        use_stub_hotkey: Whether to force stub hotkey behavior.
        backend: Optional backend mode override.
        output_mode: Optional output destination override.

    Returns:
        DictationService: Service wired with selected runtime components.

    Raises:
        RuntimeError: If runtime dependencies for selected backends are unavailable.
        ValueError: If unsupported backend or output mode is requested.

    Example:
        ``service = build_default_service(AppConfig(), simulate_trigger=True, backend="stub")``
    """

    selected_backend = backend or config.backend
    selected_output_mode = output_mode or config.output_mode

    if simulate_trigger or use_stub_hotkey:
        hotkey_capture = StubHotkeyCapture(auto_trigger_once=simulate_trigger)
    else:
        hotkey_capture = MacOSGlobalHotkeyCapture(hotkey=config.hotkey)

    audio_capture, transcription_client = _build_audio_and_transcription(
        config=config,
        backend=selected_backend,
    )
    text_injector = _build_text_injector(config=config, output_mode=selected_output_mode)

    return DictationService(
        config=config,
        hotkey_capture=hotkey_capture,
        audio_capture=audio_capture,
        transcription_client=transcription_client,
        text_injector=text_injector,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the flow-dictate CLI.

    Parameters:
        argv: Optional argument list; defaults to ``sys.argv`` when omitted.

    Returns:
        int: Process-style exit code.

    Raises:
        None.

    Example:
        ``main(["run", "--run-once", "--simulate-trigger"])``
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

    try:
        config = AppConfig.from_env()
        service = build_default_service(
            config=config,
            simulate_trigger=args.simulate_trigger,
            use_stub_hotkey=args.use_stub_hotkey,
            backend=args.backend,
            output_mode=args.output,
        )
    except (RuntimeError, ValueError) as exc:
        print(
            "flow-dictate startup error: "
            f"{exc}\n"
            "Hint: run `flow-dictate doctor` to confirm macOS permissions.",
            file=sys.stderr,
        )
        return 2

    if args.run_once:
        service.run_once(timeout_seconds=0.0)
        return 0

    service.run_forever(max_iterations=args.max_iterations)
    return 0
