"""Hotkey capture implementations for macOS and local tests."""

from __future__ import annotations

import threading
import time
from typing import Any

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


class MacOSGlobalHotkeyCapture(HotkeyCapture):
    """Listen for a global hotkey combination on macOS using ``pynput``.

    Parameters:
        hotkey: Combination in ``cmd+shift+space`` format.

    Returns:
        MacOSGlobalHotkeyCapture: Background listener-backed capture implementation.

    Raises:
        RuntimeError: If listener dependencies are unavailable or listener startup fails.
        ValueError: If the configured hotkey is malformed.

    Example:
        ``capture = MacOSGlobalHotkeyCapture(hotkey="cmd+shift+space")``
    """

    def __init__(self, hotkey: str) -> None:
        """Create and start a global hotkey listener.

        Parameters:
            hotkey: Combination in ``cmd+shift+space`` format.

        Returns:
            None.

        Raises:
            RuntimeError: If listener dependencies are unavailable or startup fails.
            ValueError: If the configured hotkey is malformed.

        Example:
            ``MacOSGlobalHotkeyCapture(hotkey="ctrl+space")``
        """

        self._required_keys = _parse_hotkey_tokens(hotkey)
        self._pressed_keys: set[str] = set()
        self._triggered_event = threading.Event()
        self._combo_armed = False
        self._listener = self._create_listener()
        self._listener.start()

    def _create_listener(self) -> Any:
        """Create the underlying ``pynput`` listener.

        Parameters:
            None.

        Returns:
            Any: ``pynput`` keyboard listener instance.

        Raises:
            RuntimeError: If listener dependency import or initialization fails.

        Example:
            ``listener = self._create_listener()``
        """

        try:
            from pynput import keyboard
        except ImportError as exc:
            raise RuntimeError(
                "pynput is required for real global hotkeys. Install project dependencies."
            ) from exc

        try:
            return keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
                suppress=False,
            )
        except Exception as exc:  # pragma: no cover - depends on macOS runtime permissions.
            raise RuntimeError(
                "Unable to start global hotkey listener. Check Input Monitoring permissions."
            ) from exc

    def _on_press(self, key: Any) -> None:
        """Track key press events and emit one trigger per full key chord.

        Parameters:
            key: Key event object from ``pynput``.

        Returns:
            None.

        Raises:
            None.

        Example:
            Internal callback only.
        """

        normalized = _normalize_listener_key(key)
        if normalized is None:
            return

        self._pressed_keys.add(normalized)

        if self._required_keys.issubset(self._pressed_keys) and not self._combo_armed:
            self._triggered_event.set()
            self._combo_armed = True

    def _on_release(self, key: Any) -> None:
        """Track key release events and re-arm trigger detection.

        Parameters:
            key: Key event object from ``pynput``.

        Returns:
            None.

        Raises:
            None.

        Example:
            Internal callback only.
        """

        normalized = _normalize_listener_key(key)
        if normalized is None:
            return

        if normalized in self._pressed_keys:
            self._pressed_keys.remove(normalized)

        if not self._required_keys.issubset(self._pressed_keys):
            self._combo_armed = False

    def wait_for_trigger(self, timeout_seconds: float | None = None) -> bool:
        """Wait for a hotkey event to be captured.

        Parameters:
            timeout_seconds: Optional timeout; ``None`` waits indefinitely.

        Returns:
            bool: ``True`` when a hotkey event is available, otherwise ``False``.

        Raises:
            ValueError: If ``timeout_seconds`` is negative.

        Example:
            ``capture.wait_for_trigger(timeout_seconds=0.2)``
        """

        if timeout_seconds is not None and timeout_seconds < 0:
            raise ValueError("timeout_seconds cannot be negative.")

        triggered = self._triggered_event.wait(timeout=timeout_seconds)
        if not triggered:
            return False

        self._triggered_event.clear()
        return True

    def close(self) -> None:
        """Stop the background listener.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``capture.close()``
        """

        self._listener.stop()


def _parse_hotkey_tokens(hotkey: str) -> set[str]:
    """Parse a hotkey expression into normalized token names.

    Parameters:
        hotkey: Combination in ``cmd+shift+space`` style format.

    Returns:
        set[str]: Normalized required token names.

    Raises:
        ValueError: If no valid tokens are found.

    Example:
        >>> _parse_hotkey_tokens("cmd+shift+space")
        {'cmd', 'shift', 'space'}
    """

    parts = [part.strip().lower() for part in hotkey.split("+") if part.strip()]
    tokens = {_normalize_hotkey_token(part) for part in parts}
    tokens = {token for token in tokens if token is not None}

    if not tokens:
        raise ValueError("Hotkey must contain at least one valid key token.")

    return tokens


def _normalize_hotkey_token(token: str) -> str | None:
    """Normalize one hotkey token to internal key representation.

    Parameters:
        token: Raw token such as ``command`` or ``space``.

    Returns:
        str | None: Normalized token, or ``None`` for unsupported tokens.

    Raises:
        None.

    Example:
        >>> _normalize_hotkey_token("command")
        'cmd'
    """

    alias_map = {
        "cmd": "cmd",
        "command": "cmd",
        "meta": "cmd",
        "shift": "shift",
        "ctrl": "ctrl",
        "control": "ctrl",
        "alt": "alt",
        "option": "alt",
        "space": "space",
        "enter": "enter",
        "return": "enter",
        "tab": "tab",
        "esc": "esc",
        "escape": "esc",
    }

    if token in alias_map:
        return alias_map[token]

    if len(token) == 1 and token.isprintable():
        return token

    return None


def _normalize_listener_key(key: Any) -> str | None:
    """Normalize a ``pynput`` key event to a token name.

    Parameters:
        key: ``pynput`` key object from listener callbacks.

    Returns:
        str | None: Normalized key name, or ``None`` if unsupported.

    Raises:
        None.

    Example:
        Internal callback utility.
    """

    # Listener keys may be KeyCode(char=...) or special Key enums. Converting to
    # string provides stable names like "Key.cmd", "Key.space", or "'a'".
    key_text = str(key).lower()

    if "key.cmd" in key_text:
        return "cmd"
    if "key.shift" in key_text:
        return "shift"
    if "key.ctrl" in key_text:
        return "ctrl"
    if "key.alt" in key_text:
        return "alt"
    if "key.space" in key_text:
        return "space"
    if "key.enter" in key_text:
        return "enter"
    if "key.tab" in key_text:
        return "tab"
    if "key.esc" in key_text:
        return "esc"

    if len(key_text) == 3 and key_text.startswith("'") and key_text.endswith("'"):
        return key_text[1]

    return None
