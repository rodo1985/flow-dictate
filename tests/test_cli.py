"""Tests for CLI helper behavior."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import flow_dictate.cli as cli_module


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
