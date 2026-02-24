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
    assert config.sample_rate_hz == 24_000
    assert config.channels == 1
    assert config.audio_input_device is None
    assert config.max_record_seconds == 30.0
    assert config.transcription_model == "gpt-4o-mini-transcribe"
    assert config.realtime_websocket_url == "wss://api.openai.com/v1/realtime"
    assert config.realtime_connect_timeout_seconds == 15.0
    assert config.realtime_response_timeout_seconds == 30.0


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
