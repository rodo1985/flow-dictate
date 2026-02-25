"""Configuration model for the flow-dictate service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

VALID_OUTPUT_MODES: tuple[str, ...] = ("stdout", "clipboard", "active-app")
VALID_BACKENDS: tuple[str, ...] = ("stub", "api", "realtime")
VALID_ACTIVE_APP_INSERTION_STRATEGIES: tuple[str, ...] = (
    "clipboard-paste",
    "direct-type",
)


def _load_dotenv_values(path: Path) -> dict[str, str]:
    """Load simple ``KEY=VALUE`` pairs from a dotenv file.

    Parameters:
        path: Path to the dotenv file.

    Returns:
        dict[str, str]: Parsed environment values.

    Raises:
        RuntimeError: If dotenv content cannot be read.

    Example:
        ``values = _load_dotenv_values(Path(".env"))``
    """

    if not path.exists():
        return {}

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Unable to read dotenv file at {path}.") from exc

    parsed: dict[str, str] = {}
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].strip()

        if "=" not in stripped:
            continue

        key, raw_value = stripped.split("=", 1)
        normalized_key = key.strip()
        if not normalized_key:
            continue

        value = raw_value.strip()
        if (
            len(value) >= 2
            and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'"))
        ):
            value = value[1:-1]

        parsed[normalized_key] = value

    return parsed


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Hold runtime configuration values for the dictation daemon.

    Parameters:
        hotkey: Human-readable global hotkey expression for triggering dictation.
        sample_rate_hz: Audio sample rate in Hertz used for recording.
        channels: Number of input audio channels.
        audio_input_device: Optional audio input device identifier for microphone capture.
        max_record_seconds: Upper bound for one dictation recording window.
        transcription_model: Transcription model identifier for OpenAI requests.
        openai_api_key_env: Environment variable name that stores the OpenAI API key.
        realtime_websocket_url: Base websocket URL used for OpenAI Realtime sessions.
        realtime_connect_timeout_seconds: Connection timeout for realtime websocket setup.
        realtime_response_timeout_seconds: Max wait time for transcription responses
            in realtime mode and HTTP transcription requests.
        temporary_audio_dir: Directory where temporary audio artifacts may be written.
        daemon_poll_interval_seconds: Poll interval used by the orchestrator loop.
        output_mode: Injector strategy for delivering text output.
        active_app_insertion_strategy: Primary insertion strategy when output mode
            is ``active-app``.
        active_app_fallback_to_clipboard: Whether active-app mode should keep clipboard output
            when auto-paste fails.
        backend: Runtime backend strategy (``stub``, ``api``, or ``realtime``).

    Returns:
        AppConfig: An immutable configuration object.

    Raises:
        ValueError: If numeric fields are non-positive or enum-like fields are invalid.

    Example:
        >>> config = AppConfig()
        >>> config.hotkey
        'cmd+shift+space'
    """

    hotkey: str = "cmd+shift+space"
    sample_rate_hz: int = 24_000
    channels: int = 1
    audio_input_device: str | None = None
    max_record_seconds: float = 30.0
    transcription_model: str = "gpt-4o-mini-transcribe"
    openai_api_key_env: str = "OPENAI_API_KEY"
    realtime_websocket_url: str = "wss://api.openai.com/v1/realtime"
    realtime_connect_timeout_seconds: float = 15.0
    realtime_response_timeout_seconds: float = 30.0
    temporary_audio_dir: Path = Path("/tmp/flow-dictate")
    daemon_poll_interval_seconds: float = 0.10
    output_mode: str = "stdout"
    active_app_insertion_strategy: str = "clipboard-paste"
    active_app_fallback_to_clipboard: bool = True
    backend: str = "stub"

    def __post_init__(self) -> None:
        """Validate runtime values immediately after initialization.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            ValueError: If any numeric or constrained string value is invalid.

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
        if self.realtime_connect_timeout_seconds <= 0:
            raise ValueError("realtime_connect_timeout_seconds must be greater than 0.")
        if self.realtime_response_timeout_seconds <= 0:
            raise ValueError("realtime_response_timeout_seconds must be greater than 0.")
        if self.daemon_poll_interval_seconds <= 0:
            raise ValueError("daemon_poll_interval_seconds must be greater than 0.")
        if not self.realtime_websocket_url:
            raise ValueError("realtime_websocket_url must not be empty.")
        if self.output_mode not in VALID_OUTPUT_MODES:
            valid_modes = ", ".join(VALID_OUTPUT_MODES)
            raise ValueError(f"output_mode must be one of: {valid_modes}.")
        if self.active_app_insertion_strategy not in VALID_ACTIVE_APP_INSERTION_STRATEGIES:
            valid_strategies = ", ".join(VALID_ACTIVE_APP_INSERTION_STRATEGIES)
            raise ValueError(
                "active_app_insertion_strategy must be one of: "
                f"{valid_strategies}."
            )
        if self.backend not in VALID_BACKENDS:
            valid_backends = ", ".join(VALID_BACKENDS)
            raise ValueError(f"backend must be one of: {valid_backends}.")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "AppConfig":
        """Create a config object from environment values.

        Parameters:
            environ: Optional mapping to use instead of ``os.environ`` for lookups.
                When omitted, values are loaded from ``.env`` in the current
                working directory and then overridden by process environment.

        Returns:
            AppConfig: Parsed config with defaults applied for missing keys.

        Raises:
            ValueError: If numeric/environment values are malformed.

        Example:
            >>> cfg = AppConfig.from_env({"FLOW_DICTATE_CHANNELS": "2"})
            >>> cfg.channels
            2
        """

        if environ is None:
            env: Mapping[str, str] = {
                **_load_dotenv_values(Path.cwd() / ".env"),
                **os.environ,
            }
        else:
            env = environ
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
        audio_input_device = _parse_optional_text(env.get("FLOW_DICTATE_AUDIO_INPUT_DEVICE"))
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
        realtime_websocket_url = (
            env.get("FLOW_DICTATE_REALTIME_WEBSOCKET_URL")
            or defaults.realtime_websocket_url
        )
        realtime_connect_timeout_seconds = _parse_positive_float(
            env.get("FLOW_DICTATE_REALTIME_CONNECT_TIMEOUT_SECONDS"),
            "FLOW_DICTATE_REALTIME_CONNECT_TIMEOUT_SECONDS",
            defaults.realtime_connect_timeout_seconds,
        )
        realtime_response_timeout_seconds = _parse_positive_float(
            env.get("FLOW_DICTATE_REALTIME_RESPONSE_TIMEOUT_SECONDS"),
            "FLOW_DICTATE_REALTIME_RESPONSE_TIMEOUT_SECONDS",
            defaults.realtime_response_timeout_seconds,
        )
        temporary_audio_dir = Path(
            env.get("FLOW_DICTATE_TEMP_AUDIO_DIR") or str(defaults.temporary_audio_dir)
        ).expanduser()
        daemon_poll_interval_seconds = _parse_positive_float(
            env.get("FLOW_DICTATE_DAEMON_POLL_INTERVAL_SECONDS"),
            "FLOW_DICTATE_DAEMON_POLL_INTERVAL_SECONDS",
            defaults.daemon_poll_interval_seconds,
        )
        output_mode = _parse_output_mode(
            env.get("FLOW_DICTATE_OUTPUT_MODE"),
            "FLOW_DICTATE_OUTPUT_MODE",
            defaults.output_mode,
        )
        active_app_insertion_strategy = _parse_active_app_insertion_strategy(
            env.get("FLOW_DICTATE_ACTIVE_APP_INSERTION_STRATEGY"),
            "FLOW_DICTATE_ACTIVE_APP_INSERTION_STRATEGY",
            defaults.active_app_insertion_strategy,
        )
        active_app_fallback_to_clipboard = _parse_bool(
            env.get("FLOW_DICTATE_ACTIVE_APP_FALLBACK_TO_CLIPBOARD"),
            "FLOW_DICTATE_ACTIVE_APP_FALLBACK_TO_CLIPBOARD",
            defaults.active_app_fallback_to_clipboard,
        )
        backend = _parse_backend(
            env.get("FLOW_DICTATE_BACKEND"),
            "FLOW_DICTATE_BACKEND",
            defaults.backend,
        )

        return cls(
            hotkey=hotkey,
            sample_rate_hz=sample_rate_hz,
            channels=channels,
            audio_input_device=audio_input_device,
            max_record_seconds=max_record_seconds,
            transcription_model=transcription_model,
            openai_api_key_env=openai_api_key_env,
            realtime_websocket_url=realtime_websocket_url,
            realtime_connect_timeout_seconds=realtime_connect_timeout_seconds,
            realtime_response_timeout_seconds=realtime_response_timeout_seconds,
            temporary_audio_dir=temporary_audio_dir,
            daemon_poll_interval_seconds=daemon_poll_interval_seconds,
            output_mode=output_mode,
            active_app_insertion_strategy=active_app_insertion_strategy,
            active_app_fallback_to_clipboard=active_app_fallback_to_clipboard,
            backend=backend,
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


def _parse_bool(raw_value: str | None, name: str, default: bool) -> bool:
    """Parse a boolean from common environment string formats.

    Parameters:
        raw_value: Raw value fetched from an environment mapping.
        name: Environment variable name used for clearer error messages.
        default: Fallback value when ``raw_value`` is missing or blank.

    Returns:
        bool: Parsed boolean value.

    Raises:
        ValueError: If ``raw_value`` is present but not a known boolean token.

    Example:
        >>> _parse_bool("true", "FLOW_DICTATE_EXAMPLE", False)
        True
    """

    if raw_value is None or raw_value == "":
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False

    raise ValueError(
        f"{name} must be one of: 1, 0, true, false, yes, no, on, off."
    )


def _parse_output_mode(raw_value: str | None, name: str, default: str) -> str:
    """Parse and validate output mode names from environment values.

    Parameters:
        raw_value: Raw value fetched from an environment mapping.
        name: Environment variable name used for clearer error messages.
        default: Fallback value when ``raw_value`` is missing or blank.

    Returns:
        str: A normalized output mode from ``VALID_OUTPUT_MODES``.

    Raises:
        ValueError: If the provided mode is not supported.

    Example:
        >>> _parse_output_mode("active-app", "FLOW_DICTATE_OUTPUT_MODE", "stdout")
        'active-app'
    """

    if raw_value is None or raw_value == "":
        return default

    normalized = raw_value.strip().lower()
    if normalized in VALID_OUTPUT_MODES:
        return normalized

    valid_modes = ", ".join(VALID_OUTPUT_MODES)
    raise ValueError(f"{name} must be one of: {valid_modes}.")


def _parse_backend(raw_value: str | None, name: str, default: str) -> str:
    """Parse and validate backend names from environment values.

    Parameters:
        raw_value: Raw value fetched from an environment mapping.
        name: Environment variable name used for clearer error messages.
        default: Fallback value when ``raw_value`` is missing or blank.

    Returns:
        str: A normalized backend from ``VALID_BACKENDS``.

    Raises:
        ValueError: If the provided backend is not supported.

    Example:
        >>> _parse_backend("realtime", "FLOW_DICTATE_BACKEND", "stub")
        'realtime'
    """

    if raw_value is None or raw_value == "":
        return default

    normalized = raw_value.strip().lower()
    if normalized in VALID_BACKENDS:
        return normalized

    valid_backends = ", ".join(VALID_BACKENDS)
    raise ValueError(f"{name} must be one of: {valid_backends}.")


def _parse_active_app_insertion_strategy(
    raw_value: str | None,
    name: str,
    default: str,
) -> str:
    """Parse active-app insertion strategy from environment values.

    Parameters:
        raw_value: Raw value fetched from an environment mapping.
        name: Environment variable name used for clearer error messages.
        default: Fallback value when ``raw_value`` is missing or blank.

    Returns:
        str: A normalized strategy from ``VALID_ACTIVE_APP_INSERTION_STRATEGIES``.

    Raises:
        ValueError: If the provided strategy is not supported.

    Example:
        >>> _parse_active_app_insertion_strategy(
        ...     "direct-type",
        ...     "FLOW_DICTATE_ACTIVE_APP_INSERTION_STRATEGY",
        ...     "clipboard-paste",
        ... )
        'direct-type'
    """

    if raw_value is None or raw_value == "":
        return default

    normalized = raw_value.strip().lower()
    if normalized in VALID_ACTIVE_APP_INSERTION_STRATEGIES:
        return normalized

    valid_strategies = ", ".join(VALID_ACTIVE_APP_INSERTION_STRATEGIES)
    raise ValueError(f"{name} must be one of: {valid_strategies}.")


def _parse_optional_text(raw_value: str | None) -> str | None:
    """Normalize optional text values from environment variables.

    Parameters:
        raw_value: Raw value fetched from an environment mapping.

    Returns:
        str | None: Stripped text when present, otherwise ``None``.

    Raises:
        None.

    Example:
        >>> _parse_optional_text("  built-in  ")
        'built-in'
    """

    if raw_value is None:
        return None

    cleaned = raw_value.strip()
    if not cleaned:
        return None

    return cleaned
