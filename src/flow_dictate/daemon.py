"""Daemon runtime helpers and JSONL event emission for app-shell integration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from typing import Any, TextIO

from flow_dictate.service import DictationService


@dataclass(frozen=True, slots=True)
class DaemonEvent:
    """Represent one daemon runtime event in the JSONL stream.

    Parameters:
        event: Stable event name consumed by external app-shells.
        occurred_at_utc: Timestamp in UTC ISO 8601 format.
        payload: Event-specific details.

    Returns:
        DaemonEvent: Immutable daemon event payload.

    Raises:
        ValueError: If ``event`` is empty.

    Example:
        >>> DaemonEvent(event="service_ready", occurred_at_utc="2026-01-01T00:00:00Z", payload={})
        DaemonEvent(event='service_ready', occurred_at_utc='2026-01-01T00:00:00Z', payload={})
    """

    event: str
    occurred_at_utc: str
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        """Validate event invariants at creation time.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            ValueError: If the event name is blank.

        Example:
            ``DaemonEvent(event="service_ready", occurred_at_utc="...", payload={})``
        """

        if not self.event.strip():
            raise ValueError("event must not be empty.")

    def to_json_line(self) -> str:
        """Encode event as one JSONL line.

        Parameters:
            None.

        Returns:
            str: Serialized one-line JSON event.

        Raises:
            TypeError: If payload values are not JSON-serializable.

        Example:
            ``line = event.to_json_line()``
        """

        return json.dumps(asdict(self), sort_keys=True)


def _utc_timestamp_iso8601() -> str:
    """Return a UTC timestamp string with trailing ``Z`` suffix.

    Parameters:
        None.

    Returns:
        str: UTC timestamp in ISO 8601 format.

    Raises:
        None.

    Example:
        ``stamp = _utc_timestamp_iso8601()``
    """

    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def map_exception_to_error_code(exc: Exception) -> str:
    """Map runtime exception types to stable daemon error codes.

    Parameters:
        exc: Raised exception from daemon lifecycle operations.

    Returns:
        str: Stable error code for telemetry and shell UI behavior.

    Raises:
        None.

    Example:
        ``code = map_exception_to_error_code(RuntimeError("boom"))``
    """

    if isinstance(exc, ValueError):
        return "E_DAEMON_CONFIG_001"
    if isinstance(exc, RuntimeError):
        return "E_DAEMON_RUNTIME_001"
    return "E_DAEMON_UNKNOWN_001"


class DaemonEventWriter:
    """Write daemon JSONL events to a text stream.

    Parameters:
        stream: Output stream receiving one event per line.

    Returns:
        DaemonEventWriter: Stream-backed event writer.

    Raises:
        None.

    Example:
        ``writer = DaemonEventWriter(stream=sys.stdout)``
    """

    def __init__(self, stream: TextIO) -> None:
        """Store stream dependency for event emission.

        Parameters:
            stream: Output stream receiving daemon JSON lines.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``DaemonEventWriter(stream=sys.stdout)``
        """

        self._stream = stream

    def emit(self, event: str, payload: dict[str, Any] | None = None) -> None:
        """Emit a generic daemon event as JSONL.

        Parameters:
            event: Stable event name.
            payload: Optional event-specific payload.

        Returns:
            None.

        Raises:
            ValueError: If event name is blank.

        Example:
            ``writer.emit("service_ready", {"backend": "api"})``
        """

        runtime_event = DaemonEvent(
            event=event,
            occurred_at_utc=_utc_timestamp_iso8601(),
            payload=payload or {},
        )
        self._stream.write(runtime_event.to_json_line() + "\n")
        self._stream.flush()

    def emit_service_ready(self, backend: str, output_mode: str) -> None:
        """Emit daemon startup readiness event.

        Parameters:
            backend: Selected transcription backend.
            output_mode: Selected output mode.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``writer.emit_service_ready(backend="api", output_mode="active-app")``
        """

        self.emit(
            event="service_ready",
            payload={
                "backend": backend,
                "output_mode": output_mode,
            },
        )

    def emit_recording_started(self) -> None:
        """Emit recording-started event.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``writer.emit_recording_started()``
        """

        self.emit(event="recording_started")

    def emit_recording_stopped(self, elapsed_seconds: float) -> None:
        """Emit recording-stopped event with duration metadata.

        Parameters:
            elapsed_seconds: Duration for captured recording segment.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``writer.emit_recording_stopped(elapsed_seconds=1.2)``
        """

        self.emit(
            event="recording_stopped",
            payload={"elapsed_seconds": round(elapsed_seconds, 3)},
        )

    def emit_transcribing_started(self) -> None:
        """Emit transcribing-started event.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``writer.emit_transcribing_started()``
        """

        self.emit(event="transcribing_started")

    def emit_transcription_completed(self, character_count: int) -> None:
        """Emit transcription-completed event with text length metadata.

        Parameters:
            character_count: Count of characters in final transcript.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``writer.emit_transcription_completed(character_count=42)``
        """

        self.emit(
            event="transcription_completed",
            payload={"character_count": character_count},
        )

    def emit_insertion_succeeded(self, method: str) -> None:
        """Emit insertion-success event.

        Parameters:
            method: Insertion method that ultimately succeeded.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``writer.emit_insertion_succeeded(method="direct-type")``
        """

        self.emit(
            event="insertion_succeeded",
            payload={"method": method},
        )

    def emit_insertion_fallback_used(self, reason: str) -> None:
        """Emit insertion-fallback-used event.

        Parameters:
            reason: Machine-readable fallback reason.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``writer.emit_insertion_fallback_used(reason="direct_typing_failed")``
        """

        self.emit(
            event="insertion_fallback_used",
            payload={"reason": reason},
        )

    def emit_error(self, code: str, message: str) -> None:
        """Emit daemon error event with stable code and message.

        Parameters:
            code: Stable daemon error code.
            message: Human-readable error details.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``writer.emit_error(code="E_DAEMON_RUNTIME_001", message="boom")``
        """

        self.emit(
            event="error",
            payload={
                "code": code,
                "message": message,
            },
        )


def run_daemon_loop(
    service: DictationService,
    *,
    poll_interval_seconds: float,
    max_iterations: int | None = None,
) -> None:
    """Run daemon polling loop for app-shell background execution.

    Parameters:
        service: Fully configured dictation service instance.
        poll_interval_seconds: Timeout passed to each trigger-wait cycle.
        max_iterations: Optional loop cap for tests and local dry runs.

    Returns:
        None.

    Raises:
        ValueError: If polling interval or iteration limits are invalid.
        RuntimeError: If downstream service dependencies fail.

    Example:
        ``run_daemon_loop(service, poll_interval_seconds=0.1, max_iterations=10)``
    """

    if poll_interval_seconds <= 0:
        raise ValueError("poll_interval_seconds must be greater than 0.")
    if max_iterations is not None and max_iterations <= 0:
        raise ValueError("max_iterations must be greater than 0 when provided.")

    iteration = 0
    while True:
        service.run_once(timeout_seconds=poll_interval_seconds)
        iteration += 1
        if max_iterations is not None and iteration >= max_iterations:
            return
