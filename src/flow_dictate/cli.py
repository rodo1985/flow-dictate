"""Command-line entrypoint for flow-dictate."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Callable, Sequence, TextIO

from flow_dictate.audio import MicrophoneAudioCapture, StubAudioCapture
from flow_dictate.config import AppConfig, VALID_BACKENDS, VALID_OUTPUT_MODES
from flow_dictate.daemon import (
    DaemonEventWriter,
    map_exception_to_error_code,
    run_daemon_loop,
)
from flow_dictate.hotkey import (
    MacOSGlobalHotkeyCapture,
    StubHotkeyCapture,
    capture_hotkey_expression,
)
from flow_dictate.injector import (
    ClipboardTextInjector,
    MacOSActiveAppTextInjector,
    StdoutTextInjector,
)
from flow_dictate.interfaces import (
    AudioCapture,
    InjectionResult,
    TextInjector,
    TranscriptionClient,
)
from flow_dictate.permissions import (
    format_preflight_report,
    preflight_report_to_dict,
    run_permission_preflight,
)
from flow_dictate.service import DictationService
from flow_dictate.transcription import (
    OpenAIAudioTranscriptionClient,
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


def _positive_float(value: str) -> float:
    """Parse a positive float for argparse options.

    Parameters:
        value: Raw CLI argument value.

    Returns:
        float: Parsed positive float.

    Raises:
        argparse.ArgumentTypeError: If value is not a positive float.

    Example:
        ``_positive_float("1.5")``
    """

    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Expected a float value.") from exc

    if parsed <= 0:
        raise argparse.ArgumentTypeError("Expected a value greater than 0.")

    return parsed


def _upsert_env_variable(env_file: Path, key: str, value: str) -> None:
    """Create or update an environment variable entry in a dotenv file.

    Parameters:
        env_file: Path to dotenv file that should be updated.
        key: Environment variable key to write.
        value: Variable value to persist.

    Returns:
        None.

    Raises:
        RuntimeError: If the dotenv file cannot be read or written.
        ValueError: If key is empty.

    Example:
        ``_upsert_env_variable(Path(".env"), "FLOW_DICTATE_HOTKEY", "ctrl+cmd")``
    """

    if not key.strip():
        raise ValueError("key must not be empty.")

    existing_lines: list[str] = []
    if env_file.exists():
        try:
            existing_lines = env_file.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise RuntimeError(f"Unable to read dotenv file at {env_file}.") from exc

    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    replacement_line = f"{key}={value}"
    updated_lines: list[str] = []
    replaced = False

    for line in existing_lines:
        if not replaced and pattern.match(line):
            updated_lines.append(replacement_line)
            replaced = True
            continue
        updated_lines.append(line)

    if not replaced:
        if updated_lines and updated_lines[-1].strip():
            updated_lines.append("")
        updated_lines.append(replacement_line)

    content = "\n".join(updated_lines).rstrip() + "\n"
    try:
        env_file.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Unable to write dotenv file at {env_file}.") from exc


class _ConsoleRecordingIndicator:
    """Render recording status messages in terminal output.

    Parameters:
        stream: Output stream used for status text.

    Returns:
        _ConsoleRecordingIndicator: Stream-backed status renderer.

    Raises:
        None.

    Example:
        ``indicator = _ConsoleRecordingIndicator(stream=sys.stderr)``
    """

    def __init__(self, stream: TextIO | None = None) -> None:
        """Initialize indicator state.

        Parameters:
            stream: Optional target stream; defaults to ``sys.stderr``.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``_ConsoleRecordingIndicator()``
        """

        self._stream = stream if stream is not None else sys.stderr
        self._active = False

    def start(self) -> None:
        """Print a terminal message indicating recording has started.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``indicator.start()``
        """

        if self._active:
            return

        self._active = True
        print(
            "flow-dictate: Recording... release hotkey to stop.",
            file=self._stream,
            flush=True,
        )

    def stop(self, elapsed_seconds: float) -> None:
        """Stop updates and print final capture + transcription status.

        Parameters:
            elapsed_seconds: Total recording duration in seconds.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``indicator.stop(elapsed_seconds=2.4)``
        """

        if not self._active:
            return

        self._active = False
        print(
            (
                "flow-dictate: Recording stopped after "
                f"{elapsed_seconds:.2f}s. Transcribing..."
            ),
            file=self._stream,
            flush=True,
        )


class _DaemonRuntimeEventBridge:
    """Bridge service callbacks into daemon JSONL runtime events.

    Parameters:
        writer: Event writer used for daemon JSONL output.

    Returns:
        _DaemonRuntimeEventBridge: Callback adapter for ``DictationService`` hooks.

    Raises:
        None.

    Example:
        ``bridge = _DaemonRuntimeEventBridge(writer)``
    """

    def __init__(self, writer: DaemonEventWriter) -> None:
        """Store daemon event writer dependency.

        Parameters:
            writer: Event writer used for daemon JSONL output.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``_DaemonRuntimeEventBridge(writer)``
        """

        self._writer = writer

    def on_recording_started(self) -> None:
        """Emit recording-start event.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``bridge.on_recording_started()``
        """

        self._writer.emit_recording_started()

    def on_recording_stopped(self, elapsed_seconds: float) -> None:
        """Emit recording-stopped event with elapsed duration.

        Parameters:
            elapsed_seconds: Recording duration in seconds.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``bridge.on_recording_stopped(elapsed_seconds=1.5)``
        """

        self._writer.emit_recording_stopped(elapsed_seconds=elapsed_seconds)

    def on_transcription_started(self) -> None:
        """Emit transcribing-started event.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``bridge.on_transcription_started()``
        """

        self._writer.emit_transcribing_started()

    def on_transcription_completed(self, transcription: str) -> None:
        """Emit transcription-completed event with character count.

        Parameters:
            transcription: Final transcription text.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``bridge.on_transcription_completed("hello")``
        """

        self._writer.emit_transcription_completed(character_count=len(transcription))

    def on_injection_completed(self, injection_result: InjectionResult) -> None:
        """Emit insertion events from injection outcome metadata.

        Parameters:
            injection_result: Structured insertion result produced by injector.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``bridge.on_injection_completed(InjectionResult(inserted=True, method="stdout"))``
        """

        if injection_result.inserted:
            self._writer.emit_insertion_succeeded(method=injection_result.method)
        if injection_result.fallback_used and injection_result.fallback_reason is not None:
            self._writer.emit_insertion_fallback_used(
                reason=injection_result.fallback_reason
            )


def _add_runtime_command_arguments(
    parser: argparse.ArgumentParser,
    output_help_default: str,
) -> None:
    """Attach shared runtime options for ``run`` and ``daemon`` commands.

    Parameters:
        parser: Parser receiving shared runtime arguments.
        output_help_default: Help-text describing output-mode default behavior.

    Returns:
        None.

    Raises:
        None.

    Example:
        ``_add_runtime_command_arguments(run_parser, output_help_default="stdout")``
    """

    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run a single orchestration cycle instead of a loop.",
    )
    parser.add_argument(
        "--simulate-trigger",
        action="store_true",
        help="Force the first hotkey wait to trigger in dry-run mode.",
    )
    parser.add_argument(
        "--use-stub-hotkey",
        action="store_true",
        help="Force the stub hotkey listener instead of global macOS capture.",
    )
    parser.add_argument(
        "--max-iterations",
        type=_positive_int,
        default=None,
        help="Stop the loop after N iterations (useful for local dry runs).",
    )
    parser.add_argument(
        "--backend",
        choices=VALID_BACKENDS,
        default=None,
        help=(
            "Backend override. "
            "Defaults to FLOW_DICTATE_BACKEND or 'stub'."
        ),
    )
    parser.add_argument(
        "--output",
        choices=VALID_OUTPUT_MODES,
        default=None,
        help=f"Output destination override. {output_help_default}",
    )


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
    _add_runtime_command_arguments(
        run_parser,
        output_help_default="Defaults to FLOW_DICTATE_OUTPUT_MODE or 'stdout'.",
    )

    daemon_parser = subparsers.add_parser(
        "daemon",
        help="Run daemon mode with JSONL runtime events for app-shell integration.",
    )
    _add_runtime_command_arguments(
        daemon_parser,
        output_help_default="Defaults to 'active-app' unless --output is provided.",
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
    doctor_parser.add_argument(
        "--json",
        action="store_true",
        help="Render preflight report as machine-readable JSON.",
    )

    hotkey_setup_parser = subparsers.add_parser(
        "hotkey-setup",
        help="Capture a hotkey chord from keyboard input and save it to .env.",
    )
    hotkey_setup_parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Dotenv file to update (default: ./.env).",
    )
    hotkey_setup_parser.add_argument(
        "--timeout-seconds",
        type=_positive_float,
        default=15.0,
        help="Maximum wait for key press/release while capturing hotkey.",
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
            insertion_strategy=config.active_app_insertion_strategy,
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
        backend: Backend mode (``stub``, ``api``, or ``realtime``).

    Returns:
        tuple[AudioCapture, TranscriptionClient]: Configured backend pair.

    Raises:
        ValueError: If backend is unsupported.
        RuntimeError: If backend dependencies are unavailable.

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

    if backend == "api":
        return (
            MicrophoneAudioCapture(
                sample_rate_hz=config.sample_rate_hz,
                channels=config.channels,
                device=config.audio_input_device,
            ),
            OpenAIAudioTranscriptionClient.from_config(config=config),
        )

    valid_backends = ", ".join(VALID_BACKENDS)
    raise ValueError(f"Unsupported backend: {backend}. Valid backends: {valid_backends}.")


def _run_hotkey_setup(env_file: Path, timeout_seconds: float) -> int:
    """Capture a hotkey chord and persist it to a dotenv file.

    Parameters:
        env_file: Dotenv file path where hotkey should be stored.
        timeout_seconds: Maximum wait for interactive key capture.

    Returns:
        int: CLI process exit code.

    Raises:
        RuntimeError: If hotkey capture or dotenv write fails.

    Example:
        ``_run_hotkey_setup(env_file=Path(".env"), timeout_seconds=15.0)``
    """

    print(
        "flow-dictate: Press your desired hotkey combination now, "
        "then release all keys to save it."
    )
    captured_hotkey = capture_hotkey_expression(timeout_seconds=timeout_seconds)
    _upsert_env_variable(env_file=env_file, key="FLOW_DICTATE_HOTKEY", value=captured_hotkey)
    print(f"flow-dictate: Saved FLOW_DICTATE_HOTKEY={captured_hotkey} to {env_file}.")
    return 0


def build_default_service(
    config: AppConfig,
    simulate_trigger: bool = False,
    use_stub_hotkey: bool = False,
    backend: str | None = None,
    output_mode: str | None = None,
    recording_indicator: _ConsoleRecordingIndicator | None = None,
    on_recording_started: Callable[[], None] | None = None,
    on_recording_stopped: Callable[[float], None] | None = None,
    on_transcription_started: Callable[[], None] | None = None,
    on_transcription_completed: Callable[[str], None] | None = None,
    on_injection_completed: Callable[[InjectionResult], None] | None = None,
) -> DictationService:
    """Create a default orchestrator using configured runtime implementations.

    Parameters:
        config: Runtime configuration values for the service.
        simulate_trigger: Whether the first hotkey wait auto-triggers.
        use_stub_hotkey: Whether to force stub hotkey behavior.
        backend: Optional backend mode override.
        output_mode: Optional output destination override.
        recording_indicator: Optional terminal indicator for active recording.
        on_recording_started: Optional callback fired right before recording begins.
        on_recording_stopped: Optional callback fired after recording stops.
        on_transcription_started: Optional callback fired before transcription begins.
        on_transcription_completed: Optional callback fired after transcription is produced.
        on_injection_completed: Optional callback fired when insertion result is available.

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
        on_recording_started=(
            on_recording_started
            if on_recording_started is not None
            else (recording_indicator.start if recording_indicator is not None else None)
        ),
        on_recording_stopped=(
            on_recording_stopped
            if on_recording_stopped is not None
            else (recording_indicator.stop if recording_indicator is not None else None)
        ),
        on_transcription_started=on_transcription_started,
        on_transcription_completed=on_transcription_completed,
        on_injection_completed=on_injection_completed,
    )


def _run_doctor_command(prompt_permissions: bool, json_output: bool) -> int:
    """Execute permission preflight doctor command.

    Parameters:
        prompt_permissions: Whether checks may trigger macOS permission prompts.
        json_output: Whether to emit machine-readable JSON.

    Returns:
        int: Process-style exit code.

    Raises:
        None.

    Example:
        ``_run_doctor_command(prompt_permissions=False, json_output=True)``
    """

    report = run_permission_preflight(prompt=prompt_permissions)
    if json_output:
        print(json.dumps(preflight_report_to_dict(report), sort_keys=True))
    else:
        print(format_preflight_report(report))
    return 0 if report.all_required_granted else 1


def _run_daemon_command(args: argparse.Namespace) -> int:
    """Execute daemon mode with JSONL runtime event output.

    Parameters:
        args: Parsed command arguments from argparse.

    Returns:
        int: Process-style exit code.

    Raises:
        None.

    Example:
        ``_run_daemon_command(args)``
    """

    writer = DaemonEventWriter(stream=sys.stdout)

    try:
        config = AppConfig.from_env()
        selected_backend = args.backend or config.backend
        # Daemon mode is primarily consumed by external app shells, so we default to
        # active-app insertion unless explicitly overridden.
        selected_output_mode = args.output or "active-app"
        selected_insertion_strategy = config.active_app_insertion_strategy
        config_source = (
            os.environ.get("FLOW_DICTATE_DAEMON_CONFIG_SOURCE", "env").strip() or "env"
        )
        bridge = _DaemonRuntimeEventBridge(writer=writer)
        service = build_default_service(
            config=config,
            simulate_trigger=args.simulate_trigger,
            use_stub_hotkey=args.use_stub_hotkey,
            backend=args.backend,
            output_mode=selected_output_mode,
            recording_indicator=None,
            on_recording_started=bridge.on_recording_started,
            on_recording_stopped=bridge.on_recording_stopped,
            on_transcription_started=bridge.on_transcription_started,
            on_transcription_completed=bridge.on_transcription_completed,
            on_injection_completed=bridge.on_injection_completed,
        )
    except (RuntimeError, ValueError) as exc:
        writer.emit_error(code=map_exception_to_error_code(exc), message=str(exc))
        print(f"flow-dictate daemon startup error: {exc}", file=sys.stderr)
        return 2

    writer.emit_service_ready(
        backend=selected_backend,
        output_mode=selected_output_mode,
        hotkey=config.hotkey,
        insertion_strategy=selected_insertion_strategy,
        config_source=config_source,
    )

    try:
        if args.run_once:
            service.run_once(timeout_seconds=0.0)
            return 0

        run_daemon_loop(
            service,
            poll_interval_seconds=config.daemon_poll_interval_seconds,
            max_iterations=args.max_iterations,
        )
        return 0
    except (RuntimeError, ValueError) as exc:
        writer.emit_error(code=map_exception_to_error_code(exc), message=str(exc))
        print(f"flow-dictate daemon runtime error: {exc}", file=sys.stderr)
        return 3


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
        return _run_doctor_command(
            prompt_permissions=args.prompt_permissions,
            json_output=args.json,
        )

    if args.command == "hotkey-setup":
        try:
            return _run_hotkey_setup(
                env_file=args.env_file,
                timeout_seconds=args.timeout_seconds,
            )
        except (RuntimeError, ValueError) as exc:
            print(f"flow-dictate hotkey setup error: {exc}", file=sys.stderr)
            return 2

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "daemon":
        return _run_daemon_command(args=args)

    try:
        config = AppConfig.from_env()
        recording_indicator = _ConsoleRecordingIndicator()
        service = build_default_service(
            config=config,
            simulate_trigger=args.simulate_trigger,
            use_stub_hotkey=args.use_stub_hotkey,
            backend=args.backend,
            output_mode=args.output,
            recording_indicator=recording_indicator,
        )
    except (RuntimeError, ValueError) as exc:
        print(
            "flow-dictate startup error: "
            f"{exc}\n"
            "Hint: run `flow-dictate doctor` to confirm macOS permissions.",
            file=sys.stderr,
        )
        return 2

    try:
        if args.run_once:
            service.run_once(timeout_seconds=0.0)
            return 0

        service.run_forever(max_iterations=args.max_iterations)
        return 0
    except (RuntimeError, ValueError) as exc:
        print(f"flow-dictate runtime error: {exc}", file=sys.stderr)
        if "realtime mode" in str(exc).lower():
            print(
                "Hint: use `flow-dictate run --backend api` for non-realtime transcription.",
                file=sys.stderr,
            )
        return 3
