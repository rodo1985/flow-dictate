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
