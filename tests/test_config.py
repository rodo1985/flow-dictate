"""Tests for configuration parsing behavior."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from flow_dictate.config import AppConfig


def test_from_env_uses_dataclass_defaults_when_env_missing() -> None:
    """Verify ``from_env`` returns valid defaults when env values are absent.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If defaults are not preserved correctly.

    Example:
        ``pytest -k test_from_env_uses_dataclass_defaults_when_env_missing``
    """

    config = AppConfig.from_env({})

    assert config.hotkey == "cmd+shift+space"
    assert config.sample_rate_hz == 24_000
    assert config.channels == 1
    assert config.audio_input_device is None
    assert config.max_record_seconds == 30.0
    assert config.transcription_model == "gpt-4o-mini-transcribe"
    assert config.realtime_websocket_url == "wss://api.openai.com/v1/realtime"
    assert config.realtime_connect_timeout_seconds == 15.0
    assert config.realtime_response_timeout_seconds == 30.0
    assert config.output_mode == "stdout"
    assert config.active_app_insertion_strategy == "clipboard-paste"
    assert config.active_app_fallback_to_clipboard is True
    assert config.backend == "stub"


def test_from_env_rejects_invalid_numeric_values() -> None:
    """Verify invalid numeric env values raise a clear ``ValueError``.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If no exception is raised for invalid values.

    Example:
        ``pytest -k test_from_env_rejects_invalid_numeric_values``
    """

    with pytest.raises(ValueError, match="FLOW_DICTATE_SAMPLE_RATE_HZ"):
        AppConfig.from_env({"FLOW_DICTATE_SAMPLE_RATE_HZ": "zero"})


def test_from_env_parses_output_and_fallback_settings() -> None:
    """Verify output-mode and fallback-related config is parsed from environment.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If parsed values differ from expected settings.

    Example:
        ``pytest -k test_from_env_parses_output_and_fallback_settings``
    """

    config = AppConfig.from_env(
        {
            "FLOW_DICTATE_OUTPUT_MODE": "active-app",
            "FLOW_DICTATE_ACTIVE_APP_INSERTION_STRATEGY": "direct-type",
            "FLOW_DICTATE_ACTIVE_APP_FALLBACK_TO_CLIPBOARD": "false",
        }
    )

    assert config.output_mode == "active-app"
    assert config.active_app_insertion_strategy == "direct-type"
    assert config.active_app_fallback_to_clipboard is False


def test_from_env_rejects_invalid_output_mode() -> None:
    """Verify unsupported output modes raise a clear ``ValueError``.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If invalid output mode is accepted.

    Example:
        ``pytest -k test_from_env_rejects_invalid_output_mode``
    """

    with pytest.raises(ValueError, match="FLOW_DICTATE_OUTPUT_MODE"):
        AppConfig.from_env({"FLOW_DICTATE_OUTPUT_MODE": "printer"})


def test_from_env_rejects_invalid_active_app_insertion_strategy() -> None:
    """Verify unsupported insertion strategies raise a clear ``ValueError``.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If invalid insertion strategy is accepted.

    Example:
        ``pytest -k test_from_env_rejects_invalid_active_app_insertion_strategy``
    """

    with pytest.raises(ValueError, match="FLOW_DICTATE_ACTIVE_APP_INSERTION_STRATEGY"):
        AppConfig.from_env(
            {"FLOW_DICTATE_ACTIVE_APP_INSERTION_STRATEGY": "telepathy"}
        )


def test_from_env_parses_optional_audio_input_device() -> None:
    """Verify optional audio device configuration is normalized correctly.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If optional device values are not normalized.

    Example:
        ``pytest -k test_from_env_parses_optional_audio_input_device``
    """

    config = AppConfig.from_env({"FLOW_DICTATE_AUDIO_INPUT_DEVICE": "  BlackHole 2ch  "})
    empty_config = AppConfig.from_env({"FLOW_DICTATE_AUDIO_INPUT_DEVICE": "   "})

    assert config.audio_input_device == "BlackHole 2ch"
    assert empty_config.audio_input_device is None


def test_from_env_parses_backend_setting() -> None:
    """Verify backend mode parsing supports valid values.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If backend parsing regresses.

    Example:
        ``pytest -k test_from_env_parses_backend_setting``
    """

    realtime_config = AppConfig.from_env({"FLOW_DICTATE_BACKEND": "realtime"})
    api_config = AppConfig.from_env({"FLOW_DICTATE_BACKEND": "api"})

    assert realtime_config.backend == "realtime"
    assert api_config.backend == "api"


def test_from_env_rejects_invalid_backend_setting() -> None:
    """Verify unsupported backend values raise a clear ``ValueError``.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If invalid backend value is accepted.

    Example:
        ``pytest -k test_from_env_rejects_invalid_backend_setting``
    """

    with pytest.raises(ValueError, match="FLOW_DICTATE_BACKEND"):
        AppConfig.from_env({"FLOW_DICTATE_BACKEND": "unsupported"})


def test_from_env_loads_dotenv_from_cwd(monkeypatch: Any, tmp_path: Path) -> None:
    """Verify ``from_env`` reads ``.env`` when no explicit mapping is provided.

    Parameters:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory fixture.

    Returns:
        None.

    Raises:
        AssertionError: If dotenv-backed values are not loaded.

    Example:
        ``pytest -k test_from_env_loads_dotenv_from_cwd``
    """

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("FLOW_DICTATE_BACKEND=realtime\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FLOW_DICTATE_BACKEND", raising=False)

    config = AppConfig.from_env()

    assert config.backend == "realtime"


def test_from_env_prefers_process_env_over_dotenv(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """Verify process environment values override values loaded from ``.env``.

    Parameters:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory fixture.

    Returns:
        None.

    Raises:
        AssertionError: If process env precedence regresses.

    Example:
        ``pytest -k test_from_env_prefers_process_env_over_dotenv``
    """

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("FLOW_DICTATE_OUTPUT_MODE=stdout\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FLOW_DICTATE_OUTPUT_MODE", "clipboard")

    config = AppConfig.from_env()

    assert config.output_mode == "clipboard"
