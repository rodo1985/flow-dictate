"""Tests for hotkey parsing and normalization helpers."""

from __future__ import annotations

import pytest

from flow_dictate.hotkey import _normalize_hotkey_token, _normalize_listener_key, _parse_hotkey_tokens


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
