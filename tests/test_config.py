"""Tests for configuration parsing behavior."""

from __future__ import annotations

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
    assert config.sample_rate_hz == 16_000
    assert config.channels == 1
    assert config.max_record_seconds == 30.0
    assert config.transcription_model == "gpt-4o-mini-transcribe"
    assert config.output_mode == "stdout"
    assert config.active_app_fallback_to_clipboard is True


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
            "FLOW_DICTATE_ACTIVE_APP_FALLBACK_TO_CLIPBOARD": "false",
        }
    )

    assert config.output_mode == "active-app"
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
