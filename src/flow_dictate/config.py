"""Configuration model for the flow-dictate service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Hold runtime configuration values for the dictation daemon.

    Parameters:
        hotkey: Human-readable global hotkey expression for triggering dictation.
        sample_rate_hz: Audio sample rate in Hertz used for recording.
        channels: Number of input audio channels.
        max_record_seconds: Upper bound for one dictation recording window.
        transcription_model: Transcription model identifier for OpenAI requests.
        openai_api_key_env: Environment variable name that stores the OpenAI API key.
        temporary_audio_dir: Directory where temporary audio artifacts may be written.
        daemon_poll_interval_seconds: Poll interval used by the orchestrator loop.

    Returns:
        AppConfig: An immutable configuration object.

    Raises:
        ValueError: If numeric fields are set to non-positive values.

    Example:
        >>> config = AppConfig()
        >>> config.hotkey
        'cmd+shift+space'
    """

    hotkey: str = "cmd+shift+space"
    sample_rate_hz: int = 16_000
    channels: int = 1
    max_record_seconds: float = 30.0
    transcription_model: str = "gpt-4o-mini-transcribe"
    openai_api_key_env: str = "OPENAI_API_KEY"
    temporary_audio_dir: Path = Path("/tmp/flow-dictate")
    daemon_poll_interval_seconds: float = 0.10

    def __post_init__(self) -> None:
        """Validate runtime values immediately after initialization.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            ValueError: If any numeric configuration is invalid.

        Example:
            >>> AppConfig(sample_rate_hz=0)
            Traceback (most recent call last):
                ...
            ValueError: sample_rate_hz must be greater than 0.
        """

        if self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be greater than 0.")
        if self.channels <= 0:
            raise ValueError("channels must be greater than 0.")
        if self.max_record_seconds <= 0:
            raise ValueError("max_record_seconds must be greater than 0.")
        if self.daemon_poll_interval_seconds <= 0:
            raise ValueError("daemon_poll_interval_seconds must be greater than 0.")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "AppConfig":
        """Create a config object from environment values.

        Parameters:
            environ: Optional mapping to use instead of ``os.environ`` for lookups.

        Returns:
            AppConfig: Parsed config with defaults applied for missing keys.

        Raises:
            ValueError: If numeric environment values are present but malformed.

        Example:
            >>> cfg = AppConfig.from_env({"FLOW_DICTATE_CHANNELS": "2"})
            >>> cfg.channels
            2
        """

        env = environ if environ is not None else os.environ
        defaults = cls()

        # Empty strings are treated as "not configured" so defaults continue to work.
        hotkey = env.get("FLOW_DICTATE_HOTKEY") or defaults.hotkey
        sample_rate_hz = _parse_positive_int(
            env.get("FLOW_DICTATE_SAMPLE_RATE_HZ"),
            "FLOW_DICTATE_SAMPLE_RATE_HZ",
            defaults.sample_rate_hz,
        )
        channels = _parse_positive_int(
            env.get("FLOW_DICTATE_CHANNELS"),
            "FLOW_DICTATE_CHANNELS",
            defaults.channels,
        )
        max_record_seconds = _parse_positive_float(
            env.get("FLOW_DICTATE_MAX_RECORD_SECONDS"),
            "FLOW_DICTATE_MAX_RECORD_SECONDS",
            defaults.max_record_seconds,
        )
        transcription_model = (
            env.get("FLOW_DICTATE_TRANSCRIPTION_MODEL") or defaults.transcription_model
        )
        openai_api_key_env = (
            env.get("FLOW_DICTATE_OPENAI_API_KEY_ENV") or defaults.openai_api_key_env
        )
        temporary_audio_dir = Path(
            env.get("FLOW_DICTATE_TEMP_AUDIO_DIR") or str(defaults.temporary_audio_dir)
        ).expanduser()
        daemon_poll_interval_seconds = _parse_positive_float(
            env.get("FLOW_DICTATE_DAEMON_POLL_INTERVAL_SECONDS"),
            "FLOW_DICTATE_DAEMON_POLL_INTERVAL_SECONDS",
            defaults.daemon_poll_interval_seconds,
        )

        return cls(
            hotkey=hotkey,
            sample_rate_hz=sample_rate_hz,
            channels=channels,
            max_record_seconds=max_record_seconds,
            transcription_model=transcription_model,
            openai_api_key_env=openai_api_key_env,
            temporary_audio_dir=temporary_audio_dir,
            daemon_poll_interval_seconds=daemon_poll_interval_seconds,
        )


def _parse_positive_int(raw_value: str | None, name: str, default: int) -> int:
    """Parse a positive integer from environment text.

    Parameters:
        raw_value: Raw value fetched from an environment mapping.
        name: Environment variable name used for clearer error messages.
        default: Fallback value when ``raw_value`` is missing or blank.

    Returns:
        int: A validated positive integer.

    Raises:
        ValueError: If parsing fails or value is not strictly positive.

    Example:
        >>> _parse_positive_int("3", "FLOW_DICTATE_CHANNELS", 1)
        3
    """

    if raw_value is None or raw_value == "":
        return default

    try:
        parsed = int(raw_value)
    except ValueError as exc:  # pragma: no cover - defensive error wrapping.
        raise ValueError(f"{name} must be an integer.") from exc

    if parsed <= 0:
        raise ValueError(f"{name} must be greater than 0.")

    return parsed


def _parse_positive_float(raw_value: str | None, name: str, default: float) -> float:
    """Parse a positive float from environment text.

    Parameters:
        raw_value: Raw value fetched from an environment mapping.
        name: Environment variable name used for clearer error messages.
        default: Fallback value when ``raw_value`` is missing or blank.

    Returns:
        float: A validated positive float.

    Raises:
        ValueError: If parsing fails or value is not strictly positive.

    Example:
        >>> _parse_positive_float("0.5", "FLOW_DICTATE_MAX_RECORD_SECONDS", 1.0)
        0.5
    """

    if raw_value is None or raw_value == "":
        return default

    try:
        parsed = float(raw_value)
    except ValueError as exc:  # pragma: no cover - defensive error wrapping.
        raise ValueError(f"{name} must be a float.") from exc

    if parsed <= 0:
        raise ValueError(f"{name} must be greater than 0.")

    return parsed
