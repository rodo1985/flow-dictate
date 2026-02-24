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

    def __init__(
        self,
        auto_trigger_once: bool = False,
        auto_hold_seconds: float = 0.25,
    ) -> None:
        """Initialize the stub capture state.

        Parameters:
            auto_trigger_once: Whether the first wait should auto-trigger.
            auto_hold_seconds: Simulated key-hold duration for each trigger.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``StubHotkeyCapture(auto_trigger_once=False)``
        """

        if auto_hold_seconds <= 0:
            raise ValueError("auto_hold_seconds must be greater than 0.")

        self._manual_triggered = False
        self._auto_trigger_once = auto_trigger_once
        self._auto_trigger_consumed = False
        self._auto_hold_seconds = auto_hold_seconds
        self._pressed_until_monotonic = 0.0

    def trigger(self, hold_seconds: float | None = None) -> None:
        """Manually fire one hotkey event.

        Parameters:
            hold_seconds: Optional hold duration to simulate for this trigger.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``capture.trigger()``
        """

        if hold_seconds is not None and hold_seconds <= 0:
            raise ValueError("hold_seconds must be greater than 0 when provided.")

        self._manual_triggered = True
        self._pressed_until_monotonic = (
            time.monotonic() + (hold_seconds or self._auto_hold_seconds)
        )

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
            # Keep the existing hold deadline configured by ``trigger``.
            if self._pressed_until_monotonic <= time.monotonic():
                self._pressed_until_monotonic = (
                    time.monotonic() + self._auto_hold_seconds
                )
            return True

        if self._auto_trigger_once and not self._auto_trigger_consumed:
            self._auto_trigger_consumed = True
            self._pressed_until_monotonic = time.monotonic() + self._auto_hold_seconds
            return True

        if timeout_seconds and timeout_seconds > 0:
            # A very short sleep makes loop behavior closer to real listeners.
            time.sleep(min(timeout_seconds, 0.01))

        return False

    def is_pressed(self) -> bool:
        """Return whether the simulated hotkey is currently held down.

        Parameters:
            None.

        Returns:
            bool: ``True`` while the simulated hold window is active.

        Raises:
            None.

        Example:
            ``capture.is_pressed()``
        """

        return time.monotonic() < self._pressed_until_monotonic


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
        self._state_lock = threading.Lock()
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

        with self._state_lock:
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

        with self._state_lock:
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

    def is_pressed(self) -> bool:
        """Return whether the configured key chord is currently held.

        Parameters:
            None.

        Returns:
            bool: ``True`` when all required hotkey tokens are currently pressed.

        Raises:
            None.

        Example:
            ``capture.is_pressed()``
        """

        with self._state_lock:
            return self._required_keys.issubset(self._pressed_keys)


def _sort_hotkey_tokens(tokens: set[str]) -> list[str]:
    """Sort hotkey tokens into a stable human-readable order.

    Parameters:
        tokens: Normalized token set.

    Returns:
        list[str]: Ordered token list suitable for config persistence.

    Raises:
        None.

    Example:
        >>> _sort_hotkey_tokens({"space", "cmd", "ctrl"})
        ['ctrl', 'cmd', 'space']
    """

    modifier_order = {"ctrl": 0, "cmd": 1, "shift": 2, "alt": 3}
    special_order = {"space": 10, "enter": 11, "tab": 12, "esc": 13}

    def _token_priority(token: str) -> tuple[int, int, str]:
        if token in modifier_order:
            return (0, modifier_order[token], token)
        if token in special_order:
            return (1, special_order[token], token)
        return (2, 0, token)

    return sorted(tokens, key=_token_priority)


def format_hotkey_expression(tokens: set[str]) -> str:
    """Convert normalized token names into ``+``-joined hotkey text.

    Parameters:
        tokens: Normalized token set.

    Returns:
        str: Hotkey expression in canonical order.

    Raises:
        ValueError: If token set is empty.

    Example:
        >>> format_hotkey_expression({"cmd", "ctrl"})
        'ctrl+cmd'
    """

    if not tokens:
        raise ValueError("tokens must contain at least one key.")

    return "+".join(_sort_hotkey_tokens(tokens))


def capture_hotkey_expression(timeout_seconds: float = 15.0) -> str:
    """Capture a hotkey chord from live keyboard input and return its expression.

    Parameters:
        timeout_seconds: Max wait for key press and release completion.

    Returns:
        str: Captured hotkey expression such as ``ctrl+cmd+space``.

    Raises:
        RuntimeError: If listener dependencies are missing or capture times out.
        ValueError: If timeout is non-positive.

    Example:
        ``expression = capture_hotkey_expression(timeout_seconds=15.0)``
    """

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than 0.")

    try:
        from pynput import keyboard
    except ImportError as exc:
        raise RuntimeError(
            "pynput is required to capture hotkeys interactively. Run `uv sync` first."
        ) from exc

    currently_pressed: set[str] = set()
    captured_tokens: set[str] = set()
    capture_started = threading.Event()
    capture_completed = threading.Event()
    state_lock = threading.Lock()

    def _on_press(key: Any) -> None:
        normalized = _normalize_listener_key(key)
        if normalized is None:
            return

        with state_lock:
            currently_pressed.add(normalized)
            captured_tokens.add(normalized)
            capture_started.set()

    def _on_release(key: Any) -> bool | None:
        normalized = _normalize_listener_key(key)
        if normalized is None:
            return None

        with state_lock:
            currently_pressed.discard(normalized)

            # Capture is complete once the user has pressed at least one
            # supported token and then fully released the chord.
            if capture_started.is_set() and not currently_pressed:
                capture_completed.set()
                return False

        return None

    listener = keyboard.Listener(
        on_press=_on_press,
        on_release=_on_release,
        suppress=False,
    )
    listener.start()
    try:
        if not capture_started.wait(timeout=timeout_seconds):
            raise RuntimeError("Timed out waiting for hotkey input.")
        if not capture_completed.wait(timeout=timeout_seconds):
            raise RuntimeError("Timed out waiting for hotkey release.")
    finally:
        listener.stop()
        listener.join(timeout=0.5)

    return format_hotkey_expression(captured_tokens)


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
