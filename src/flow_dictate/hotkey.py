"""Hotkey capture stubs for local development and tests."""

from __future__ import annotations

import time

from flow_dictate.interfaces import HotkeyCapture


class StubHotkeyCapture(HotkeyCapture):
    """Provide an in-memory hotkey capture implementation.

    Parameters:
        auto_trigger_once: If ``True``, the first wait call returns ``True``.

    Returns:
        StubHotkeyCapture: A controllable hotkey trigger source for scaffolding.

    Raises:
        None.

    Example:
        >>> capture = StubHotkeyCapture(auto_trigger_once=True)
        >>> capture.wait_for_trigger(timeout_seconds=0.0)
        True
    """

    def __init__(self, auto_trigger_once: bool = False) -> None:
        """Initialize the stub capture state.

        Parameters:
            auto_trigger_once: Whether the first wait should auto-trigger.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``StubHotkeyCapture(auto_trigger_once=False)``
        """

        self._manual_triggered = False
        self._auto_trigger_once = auto_trigger_once
        self._auto_trigger_consumed = False

    def trigger(self) -> None:
        """Manually fire one hotkey event.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``capture.trigger()``
        """

        self._manual_triggered = True

    def wait_for_trigger(self, timeout_seconds: float | None = None) -> bool:
        """Return trigger state, optionally sleeping to mimic blocking IO.

        Parameters:
            timeout_seconds: Optional amount of time to wait before returning.

        Returns:
            bool: ``True`` if a manual or automatic trigger was available.

        Raises:
            ValueError: If ``timeout_seconds`` is negative.

        Example:
            ``capture.wait_for_trigger(timeout_seconds=0.1)``
        """

        if timeout_seconds is not None and timeout_seconds < 0:
            raise ValueError("timeout_seconds cannot be negative.")

        if self._manual_triggered:
            self._manual_triggered = False
            return True

        if self._auto_trigger_once and not self._auto_trigger_consumed:
            self._auto_trigger_consumed = True
            return True

        if timeout_seconds and timeout_seconds > 0:
            # A very short sleep makes loop behavior closer to real listeners.
            time.sleep(min(timeout_seconds, 0.01))

        return False
