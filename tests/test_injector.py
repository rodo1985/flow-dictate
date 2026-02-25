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


class RecordingDirectTypingTrigger:
    """Record direct-typing calls and payloads."""

    def __init__(self, events: list[str]) -> None:
        """Store shared event history for assertions.

        Parameters:
            events: Mutable event log shared with the test.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``RecordingDirectTypingTrigger(events=[])``
        """

        self._events = events

    def __call__(self, text: str) -> None:
        """Record one direct-typing operation.

        Parameters:
            text: Text payload passed to typing automation.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``trigger("hello")``
        """

        self._events.append(f"type:{text}")


class FailingDirectTypingTrigger:
    """Raise a deterministic error for direct-typing requests."""

    def __call__(self, text: str) -> None:
        """Raise deterministic direct-typing failure.

        Parameters:
            text: Text payload; unused in this fake.

        Returns:
            None.

        Raises:
            RuntimeError: Always raised to force fallback behavior.

        Example:
            ``FailingDirectTypingTrigger()("hello")``
        """

        del text
        raise RuntimeError("direct typing unavailable")


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

    result = injector.inject("hello")

    assert captured == ["hello"]
    assert result.method == "clipboard"
    assert result.inserted is True


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

    result = injector.inject("voice text")

    assert events == ["clipboard:voice text", "paste"]
    assert result.method == "clipboard-paste"
    assert result.fallback_used is False


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

    result = injector.inject("fallback text")

    assert captured == ["fallback text"]
    assert "clipboard" in warning_stream.getvalue().lower()
    assert result.fallback_used is True
    assert result.fallback_reason == "paste_trigger_failed"


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


def test_active_app_injector_direct_type_path_succeeds() -> None:
    """Verify direct-typing strategy succeeds without fallback when available.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If direct-typing strategy behavior regresses.

    Example:
        ``pytest -k test_active_app_injector_direct_type_path_succeeds``
    """

    events: list[str] = []
    injector = MacOSActiveAppTextInjector(
        clipboard_injector=ClipboardTextInjector(
            clipboard_writer=lambda text: events.append(f"clipboard:{text}")
        ),
        paste_trigger=RecordingPasteTrigger(events),
        direct_typing_trigger=RecordingDirectTypingTrigger(events),
        insertion_strategy="direct-type",
        fallback_to_clipboard=True,
        platform_name="darwin",
    )

    result = injector.inject("typed text")

    assert result.inserted is True
    assert result.method == "direct-type"
    assert result.fallback_used is False
    assert events == ["type:typed text"]


def test_active_app_injector_direct_type_falls_back_to_clipboard_path() -> None:
    """Verify direct-typing failures use clipboard+paste fallback when enabled.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If fallback behavior or reason code regresses.

    Example:
        ``pytest -k test_active_app_injector_direct_type_falls_back_to_clipboard_path``
    """

    events: list[str] = []
    warning_stream = StringIO()
    injector = MacOSActiveAppTextInjector(
        clipboard_injector=ClipboardTextInjector(
            clipboard_writer=lambda text: events.append(f"clipboard:{text}")
        ),
        paste_trigger=RecordingPasteTrigger(events),
        direct_typing_trigger=FailingDirectTypingTrigger(),
        insertion_strategy="direct-type",
        fallback_to_clipboard=True,
        warning_stream=warning_stream,
        platform_name="darwin",
    )

    result = injector.inject("fallback typing text")

    assert events == ["clipboard:fallback typing text", "paste"]
    assert "direct typing failed" in warning_stream.getvalue().lower()
    assert result.fallback_used is True
    assert result.fallback_reason == "direct_typing_failed"
