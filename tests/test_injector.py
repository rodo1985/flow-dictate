"""Tests for text injection backends and fallback behavior."""

from __future__ import annotations

from io import StringIO

import pytest

from flow_dictate.injector import ClipboardTextInjector, MacOSActiveAppTextInjector


class RecordingPasteTrigger:
    """Record when paste is requested.

    Parameters:
        events: Mutable list used to capture ordered side effects.

    Returns:
        RecordingPasteTrigger: Callable recorder for paste events.

    Raises:
        None.

    Example:
        ``trigger = RecordingPasteTrigger(events)``
    """

    def __init__(self, events: list[str]) -> None:
        """Store shared event history for assertions.

        Parameters:
            events: Mutable event log shared with the test.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``RecordingPasteTrigger(events=[])``
        """

        self._events = events

    def __call__(self) -> None:
        """Record a paste invocation.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``trigger()``
        """

        self._events.append("paste")


class FailingPasteTrigger:
    """Raise an error each time paste is requested."""

    def __call__(self) -> None:
        """Raise a deterministic paste failure.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            RuntimeError: Always, to emulate missing accessibility permissions.

        Example:
            ``FailingPasteTrigger()()``
        """

        raise RuntimeError("paste unavailable")


def test_clipboard_injector_uses_writer_callback() -> None:
    """Verify clipboard injector writes the provided text through its callback.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If expected write callback call is missing.

    Example:
        ``pytest -k test_clipboard_injector_uses_writer_callback``
    """

    captured: list[str] = []
    injector = ClipboardTextInjector(clipboard_writer=captured.append)

    injector.inject("hello")

    assert captured == ["hello"]


def test_active_app_injector_pastes_after_copying_to_clipboard() -> None:
    """Verify active-app mode first writes clipboard content, then triggers paste.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If operation order or side effects are incorrect.

    Example:
        ``pytest -k test_active_app_injector_pastes_after_copying_to_clipboard``
    """

    events: list[str] = []
    clipboard_injector = ClipboardTextInjector(
        clipboard_writer=lambda text: events.append(f"clipboard:{text}")
    )
    paste_trigger = RecordingPasteTrigger(events)
    injector = MacOSActiveAppTextInjector(
        clipboard_injector=clipboard_injector,
        paste_trigger=paste_trigger,
        fallback_to_clipboard=True,
        platform_name="darwin",
    )

    injector.inject("voice text")

    assert events == ["clipboard:voice text", "paste"]


def test_active_app_injector_falls_back_to_clipboard_on_paste_failure() -> None:
    """Verify active-app mode keeps clipboard output when paste trigger fails.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If fallback behavior does not preserve clipboard output.

    Example:
        ``pytest -k test_active_app_injector_falls_back_to_clipboard_on_paste_failure``
    """

    captured: list[str] = []
    warning_stream = StringIO()
    injector = MacOSActiveAppTextInjector(
        clipboard_injector=ClipboardTextInjector(clipboard_writer=captured.append),
        paste_trigger=FailingPasteTrigger(),
        fallback_to_clipboard=True,
        warning_stream=warning_stream,
        platform_name="darwin",
    )

    injector.inject("fallback text")

    assert captured == ["fallback text"]
    assert "clipboard" in warning_stream.getvalue().lower()


def test_active_app_injector_raises_when_fallback_disabled() -> None:
    """Verify paste failures surface when clipboard fallback is disabled.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If expected failure is not raised.

    Example:
        ``pytest -k test_active_app_injector_raises_when_fallback_disabled``
    """

    injector = MacOSActiveAppTextInjector(
        clipboard_injector=ClipboardTextInjector(clipboard_writer=lambda _text: None),
        paste_trigger=FailingPasteTrigger(),
        fallback_to_clipboard=False,
        platform_name="darwin",
    )

    with pytest.raises(RuntimeError, match="fallback is disabled"):
        injector.inject("must fail")


def test_active_app_injector_rejects_non_macos_platforms() -> None:
    """Verify active-app output fails fast when not running on macOS.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If non-macOS platform check does not trigger.

    Example:
        ``pytest -k test_active_app_injector_rejects_non_macos_platforms``
    """

    injector = MacOSActiveAppTextInjector(
        clipboard_injector=ClipboardTextInjector(clipboard_writer=lambda _text: None),
        paste_trigger=RecordingPasteTrigger(events=[]),
        fallback_to_clipboard=True,
        platform_name="linux",
    )

    with pytest.raises(RuntimeError, match="only supported on macOS"):
        injector.inject("hello")
