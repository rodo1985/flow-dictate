"""Tests for CLI helper behavior."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

import flow_dictate.cli as cli_module
from flow_dictate.interfaces import InjectionResult
from flow_dictate.permissions import PermissionCheckResult, PermissionPreflightReport


def test_upsert_env_variable_creates_and_updates_key(tmp_path: Path) -> None:
    """Verify dotenv helper writes new keys and updates existing entries.

    Parameters:
        tmp_path: Temporary directory fixture.

    Returns:
        None.

    Raises:
        AssertionError: If dotenv key upsert behavior regresses.

    Example:
        ``pytest -k test_upsert_env_variable_creates_and_updates_key``
    """

    env_file = tmp_path / ".env"

    cli_module._upsert_env_variable(
        env_file=env_file,
        key="FLOW_DICTATE_HOTKEY",
        value="ctrl+cmd",
    )
    cli_module._upsert_env_variable(
        env_file=env_file,
        key="FLOW_DICTATE_HOTKEY",
        value="cmd+shift+space",
    )

    content = env_file.read_text(encoding="utf-8")
    assert "FLOW_DICTATE_HOTKEY=cmd+shift+space" in content
    assert "FLOW_DICTATE_HOTKEY=ctrl+cmd" not in content


def test_run_hotkey_setup_captures_and_persists_hotkey(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """Verify hotkey setup command captures key input and updates dotenv.

    Parameters:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory fixture.

    Returns:
        None.

    Raises:
        AssertionError: If hotkey setup persistence behavior regresses.

    Example:
        ``pytest -k test_run_hotkey_setup_captures_and_persists_hotkey``
    """

    env_file = tmp_path / ".env"
    monkeypatch.setattr(
        cli_module,
        "capture_hotkey_expression",
        lambda timeout_seconds: "ctrl+cmd",
    )

    exit_code = cli_module._run_hotkey_setup(env_file=env_file, timeout_seconds=5.0)

    assert exit_code == 0
    assert env_file.read_text(encoding="utf-8").strip() == "FLOW_DICTATE_HOTKEY=ctrl+cmd"


def test_main_handles_runtime_error_with_backend_hint(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    """Verify CLI catches runtime failures and prints backend fallback hint.

    Parameters:
        monkeypatch: Pytest monkeypatch fixture.
        capsys: Pytest output capture fixture.

    Returns:
        None.

    Raises:
        AssertionError: If runtime-error handling output regresses.

    Example:
        ``pytest -k test_main_handles_runtime_error_with_backend_hint``
    """

    class _FailingService:
        """Raise a runtime error when service loop is started.

        Parameters:
            None.

        Returns:
            _FailingService: Deterministic failing service fake.

        Raises:
            None.

        Example:
            ``service = _FailingService()``
        """

        def run_once(self, timeout_seconds: float | None = None) -> None:
            """Provide the run-once method required by the service contract.

            Parameters:
                timeout_seconds: Optional wait timeout; unused in this fake.

            Returns:
                None.

            Raises:
                None.

            Example:
                ``service.run_once(timeout_seconds=0.0)``
            """

            del timeout_seconds

        def run_forever(self, max_iterations: int | None = None) -> None:
            """Raise deterministic runtime error for assertion coverage.

            Parameters:
                max_iterations: Optional loop limit; unused in this fake.

            Returns:
                None.

            Raises:
                RuntimeError: Always raised with realtime-model unsupported message.

            Example:
                ``service.run_forever(max_iterations=1)``
            """

            del max_iterations
            raise RuntimeError('Model "gpt-4o-mini-transcribe" is not supported in realtime mode.')

    monkeypatch.setattr(
        cli_module,
        "build_default_service",
        lambda **_: _FailingService(),
    )

    exit_code = cli_module.main(["run", "--backend", "stub", "--max-iterations", "1"])
    captured = capsys.readouterr()

    assert exit_code == 3
    assert "runtime error" in captured.err
    assert "--backend api" in captured.err


def test_doctor_json_output_uses_machine_readable_payload(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    """Verify ``doctor --json`` prints structured permission report output.

    Parameters:
        monkeypatch: Pytest monkeypatch fixture.
        capsys: Pytest output capture fixture.

    Returns:
        None.

    Raises:
        AssertionError: If JSON payload or exit code behavior regresses.

    Example:
        ``pytest -k test_doctor_json_output_uses_machine_readable_payload``
    """

    report = PermissionPreflightReport(
        microphone=PermissionCheckResult(
            name="Microphone",
            granted=True,
            state="granted",
            details="Microphone permission is granted.",
        ),
        accessibility=PermissionCheckResult(
            name="Accessibility",
            granted=True,
            state="granted",
            details="Accessibility permission is granted.",
        ),
        input_monitoring=PermissionCheckResult(
            name="Input Monitoring",
            granted=False,
            state="denied",
            details="Input Monitoring permission is denied.",
            remediation="Enable permission in System Settings.",
        ),
    )
    monkeypatch.setattr(cli_module, "run_permission_preflight", lambda prompt: report)

    exit_code = cli_module.main(["doctor", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["all_required_granted"] is False
    assert payload["input_monitoring"]["state"] == "denied"


def test_daemon_run_once_emits_service_and_lifecycle_events(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    """Verify daemon mode emits JSONL events for one successful run cycle.

    Parameters:
        monkeypatch: Pytest monkeypatch fixture.
        capsys: Pytest output capture fixture.

    Returns:
        None.

    Raises:
        AssertionError: If daemon event emission regresses.

    Example:
        ``pytest -k test_daemon_run_once_emits_service_and_lifecycle_events``
    """

    callbacks: dict[str, Any] = {}

    class _FakeService:
        """Emit callback lifecycle when run once is invoked."""

        def run_once(self, timeout_seconds: float | None = None) -> None:
            """Call injected callbacks to emulate a successful dictation cycle.

            Parameters:
                timeout_seconds: Poll timeout from daemon loop; unused in this fake.

            Returns:
                None.

            Raises:
                None.

            Example:
                ``service.run_once(timeout_seconds=0.0)``
            """

            del timeout_seconds
            callbacks["on_recording_started"]()
            callbacks["on_recording_stopped"](1.25)
            callbacks["on_transcription_started"]()
            callbacks["on_transcription_completed"]("hello world")
            callbacks["on_injection_completed"](
                InjectionResult(
                    inserted=True,
                    method="direct-type",
                    fallback_used=True,
                    fallback_reason="direct_typing_failed",
                )
            )

    def _fake_build_default_service(**kwargs: Any) -> _FakeService:
        """Capture callbacks passed by CLI and return fake service.

        Parameters:
            kwargs: Service-construction kwargs from CLI command.

        Returns:
            _FakeService: Callback-emitting service double.

        Raises:
            None.

        Example:
            ``_fake_build_default_service(config=..., on_recording_started=...)``
        """

        callbacks["on_recording_started"] = kwargs["on_recording_started"]
        callbacks["on_recording_stopped"] = kwargs["on_recording_stopped"]
        callbacks["on_transcription_started"] = kwargs["on_transcription_started"]
        callbacks["on_transcription_completed"] = kwargs["on_transcription_completed"]
        callbacks["on_injection_completed"] = kwargs["on_injection_completed"]
        return _FakeService()

    monkeypatch.setattr(cli_module, "build_default_service", _fake_build_default_service)

    exit_code = cli_module.main(["daemon", "--run-once", "--backend", "stub"])
    captured = capsys.readouterr()
    events = [
        json.loads(line)
        for line in captured.out.splitlines()
        if line.strip()
    ]

    assert exit_code == 0
    assert events[0]["event"] == "service_ready"
    assert events[1]["event"] == "recording_started"
    assert events[2]["event"] == "recording_stopped"
    assert events[3]["event"] == "transcribing_started"
    assert events[4]["event"] == "transcription_completed"
    assert events[5]["event"] == "insertion_succeeded"
    assert events[6]["event"] == "insertion_fallback_used"
