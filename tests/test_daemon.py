"""Tests for daemon runtime helpers and event formatting."""

from __future__ import annotations

from io import StringIO
import json

import pytest

from flow_dictate.daemon import (
    DaemonEventWriter,
    map_exception_to_error_code,
    run_daemon_loop,
)


class _LoopService:
    """Track ``run_once`` calls for daemon loop tests."""

    def __init__(self) -> None:
        """Initialize run-once call counter.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``service = _LoopService()``
        """

        self.calls: int = 0

    def run_once(self, timeout_seconds: float | None = None) -> None:
        """Increment call count for each loop iteration.

        Parameters:
            timeout_seconds: Poll timeout supplied by daemon loop.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``service.run_once(timeout_seconds=0.1)``
        """

        del timeout_seconds
        self.calls += 1


def test_daemon_event_writer_outputs_json_lines() -> None:
    """Verify daemon event writer emits one valid JSON line per event.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If JSONL output shape regresses.

    Example:
        ``pytest -k test_daemon_event_writer_outputs_json_lines``
    """

    stream = StringIO()
    writer = DaemonEventWriter(stream=stream)

    writer.emit_service_ready(backend="stub", output_mode="stdout")

    payload = json.loads(stream.getvalue().strip())
    assert payload["event"] == "service_ready"
    assert payload["payload"]["backend"] == "stub"


def test_map_exception_to_error_code_returns_stable_values() -> None:
    """Verify known exception classes map to expected daemon error codes.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If stable error-code mapping regresses.

    Example:
        ``pytest -k test_map_exception_to_error_code_returns_stable_values``
    """

    assert map_exception_to_error_code(ValueError("bad config")) == "E_DAEMON_CONFIG_001"
    assert map_exception_to_error_code(RuntimeError("runtime fail")) == "E_DAEMON_RUNTIME_001"
    assert map_exception_to_error_code(Exception("unknown")) == "E_DAEMON_UNKNOWN_001"


def test_run_daemon_loop_respects_iteration_limit() -> None:
    """Verify daemon loop exits after configured maximum iterations.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If iteration limit is not respected.

    Example:
        ``pytest -k test_run_daemon_loop_respects_iteration_limit``
    """

    service = _LoopService()
    run_daemon_loop(service=service, poll_interval_seconds=0.1, max_iterations=3)

    assert service.calls == 3


def test_run_daemon_loop_rejects_invalid_poll_interval() -> None:
    """Verify daemon loop rejects non-positive poll intervals.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If invalid poll interval does not raise.

    Example:
        ``pytest -k test_run_daemon_loop_rejects_invalid_poll_interval``
    """

    with pytest.raises(ValueError, match="poll_interval_seconds"):
        run_daemon_loop(service=_LoopService(), poll_interval_seconds=0.0, max_iterations=1)
