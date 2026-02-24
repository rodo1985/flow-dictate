"""Tests for hotkey parsing and normalization helpers."""

from __future__ import annotations

import time

import pytest

from flow_dictate.hotkey import (
    StubHotkeyCapture,
    _normalize_hotkey_token,
    _normalize_listener_key,
    _parse_hotkey_tokens,
    format_hotkey_expression,
)


class _DummyKey:
    """Provide controlled ``__str__`` output for listener key normalization tests.

    Parameters:
        value: String representation returned by ``__str__``.

    Returns:
        _DummyKey: Lightweight key test double.

    Raises:
        None.

    Example:
        ``key = _DummyKey("Key.cmd")``
    """

    def __init__(self, value: str) -> None:
        """Store the value used as the string representation.

        Parameters:
            value: String representation for test assertions.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``_DummyKey("Key.space")``
        """

        self._value = value

    def __str__(self) -> str:
        """Return the configured key representation string.

        Parameters:
            None.

        Returns:
            str: Stored key representation.

        Raises:
            None.

        Example:
            ``str(_DummyKey("Key.shift"))``
        """

        return self._value


def test_parse_hotkey_tokens_normalizes_aliases() -> None:
    """Verify common aliases resolve to normalized internal token names.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If aliases are not normalized correctly.

    Example:
        ``pytest -k test_parse_hotkey_tokens_normalizes_aliases``
    """

    parsed = _parse_hotkey_tokens("command+shift+space")
    assert parsed == {"cmd", "shift", "space"}


def test_parse_hotkey_tokens_requires_valid_token() -> None:
    """Verify parser rejects expressions with no supported token.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If invalid hotkey does not raise.

    Example:
        ``pytest -k test_parse_hotkey_tokens_requires_valid_token``
    """

    with pytest.raises(ValueError, match="at least one valid key token"):
        _parse_hotkey_tokens("++++")


def test_normalize_hotkey_token_single_character() -> None:
    """Verify printable one-character tokens are preserved.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If character token normalization regresses.

    Example:
        ``pytest -k test_normalize_hotkey_token_single_character``
    """

    assert _normalize_hotkey_token("k") == "k"


def test_normalize_listener_key_special_and_char_tokens() -> None:
    """Verify listener key normalization supports both special and char keys.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If key normalization output is incorrect.

    Example:
        ``pytest -k test_normalize_listener_key_special_and_char_tokens``
    """

    assert _normalize_listener_key(_DummyKey("Key.cmd")) == "cmd"
    assert _normalize_listener_key(_DummyKey("'a'")) == "a"


def test_format_hotkey_expression_orders_modifier_tokens_stably() -> None:
    """Verify formatted expression uses canonical ordering for saved hotkeys.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If canonical ordering regresses.

    Example:
        ``pytest -k test_format_hotkey_expression_orders_modifier_tokens_stably``
    """

    expression = format_hotkey_expression({"space", "cmd", "ctrl"})
    assert expression == "ctrl+cmd+space"


def test_stub_hotkey_is_pressed_during_trigger_hold_window() -> None:
    """Verify stub hotkey reports pressed state briefly after trigger.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If hold-state behavior regresses.

    Example:
        ``pytest -k test_stub_hotkey_is_pressed_during_trigger_hold_window``
    """

    capture = StubHotkeyCapture(auto_trigger_once=True, auto_hold_seconds=0.05)
    assert capture.wait_for_trigger(timeout_seconds=0.0) is True
    assert capture.is_pressed() is True
    time.sleep(0.06)
    assert capture.is_pressed() is False
