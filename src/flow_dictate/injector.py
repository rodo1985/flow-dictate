"""Text injection implementations for stdout, clipboard, and active macOS app paste."""

from __future__ import annotations

import subprocess
import sys
from typing import Callable, TextIO

from flow_dictate.interfaces import TextInjector


def _write_clipboard_with_pbcopy(text: str) -> None:
    """Write text into the macOS clipboard using ``pbcopy``.

    Parameters:
        text: Text payload that should be available for paste operations.

    Returns:
        None.

    Raises:
        RuntimeError: If ``pbcopy`` is unavailable or exits with an error.

    Example:
        ``_write_clipboard_with_pbcopy("hello world")``
    """

    try:
        process = subprocess.run(
            ["pbcopy"],
            input=text,
            text=True,
            check=False,
            capture_output=True,
        )
    except OSError as exc:
        raise RuntimeError("Unable to run pbcopy for clipboard output.") from exc

    if process.returncode != 0:
        stderr_output = process.stderr.strip()
        raise RuntimeError(f"pbcopy failed: {stderr_output or 'unknown error'}")


def _trigger_active_app_paste_with_osascript() -> None:
    """Request a Command+V keystroke in the active macOS app via AppleScript.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        RuntimeError: If ``osascript`` is unavailable or returns a non-zero exit code.

    Example:
        ``_trigger_active_app_paste_with_osascript()``
    """

    paste_script = 'tell application "System Events" to keystroke "v" using command down'

    try:
        process = subprocess.run(
            ["osascript", "-e", paste_script],
            check=False,
            text=True,
            capture_output=True,
        )
    except OSError as exc:
        raise RuntimeError("Unable to run osascript for active-app insertion.") from exc

    if process.returncode != 0:
        stderr_output = process.stderr.strip()
        raise RuntimeError(f"osascript paste trigger failed: {stderr_output or 'unknown error'}")


class StdoutTextInjector(TextInjector):
    """Write injected text to a stream instead of the macOS accessibility API.

    Parameters:
        stream: Target text stream. Defaults to ``sys.stdout``.

    Returns:
        StdoutTextInjector: Stream-backed text injector.

    Raises:
        None.

    Example:
        >>> injector = StdoutTextInjector()
        >>> injector.inject("hello")
    """

    def __init__(self, stream: TextIO | None = None) -> None:
        """Initialize injector with an optional output stream.

        Parameters:
            stream: Stream to write text output to.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``StdoutTextInjector(stream=sys.stdout)``
        """

        self._stream = stream if stream is not None else sys.stdout

    def inject(self, text: str) -> None:
        """Emit text to the configured stream.

        Parameters:
            text: Text payload to emit.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``injector.inject("transcribed text")``
        """

        print(text, file=self._stream)


class ClipboardTextInjector(TextInjector):
    """Write text to the macOS clipboard for manual or automated paste.

    Parameters:
        clipboard_writer: Optional callable used to write text into the clipboard.
            Defaults to the ``pbcopy`` implementation.

    Returns:
        ClipboardTextInjector: Clipboard-backed text injector.

    Raises:
        None.

    Example:
        ``ClipboardTextInjector().inject("text in clipboard")``
    """

    def __init__(self, clipboard_writer: Callable[[str], None] | None = None) -> None:
        """Store the clipboard writing strategy.

        Parameters:
            clipboard_writer: Optional clipboard function for testability.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``ClipboardTextInjector(clipboard_writer=my_writer)``
        """

        self._clipboard_writer = clipboard_writer or _write_clipboard_with_pbcopy

    def inject(self, text: str) -> None:
        """Write text to the clipboard.

        Parameters:
            text: Text payload to copy.

        Returns:
            None.

        Raises:
            RuntimeError: If clipboard write fails.

        Example:
            ``injector.inject("copy me")``
        """

        self._clipboard_writer(text)


class MacOSActiveAppTextInjector(TextInjector):
    """Paste text into the active macOS app with clipboard fallback.

    Parameters:
        clipboard_injector: Clipboard injector used to stage text for paste.
        paste_trigger: Callable that triggers the active-app paste action.
        fallback_to_clipboard: Whether to keep clipboard output when paste fails.
        warning_stream: Stream used for non-fatal fallback warnings.
        platform_name: Optional platform identifier for deterministic tests.

    Returns:
        MacOSActiveAppTextInjector: Active-app injector with clipboard fallback.

    Raises:
        None.

    Example:
        ``MacOSActiveAppTextInjector().inject("hello from voice")``
    """

    def __init__(
        self,
        clipboard_injector: TextInjector | None = None,
        paste_trigger: Callable[[], None] | None = None,
        fallback_to_clipboard: bool = True,
        warning_stream: TextIO | None = None,
        platform_name: str | None = None,
    ) -> None:
        """Initialize active-app insertion dependencies.

        Parameters:
            clipboard_injector: Injector used to copy text into clipboard.
            paste_trigger: Function that performs active-app paste.
            fallback_to_clipboard: Whether to suppress paste errors and keep clipboard content.
            warning_stream: Stream for warning messages on fallback.
            platform_name: Optional platform override used by tests.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``MacOSActiveAppTextInjector(fallback_to_clipboard=False)``
        """

        self._clipboard_injector = clipboard_injector or ClipboardTextInjector()
        self._paste_trigger = paste_trigger or _trigger_active_app_paste_with_osascript
        self._fallback_to_clipboard = fallback_to_clipboard
        self._warning_stream = warning_stream if warning_stream is not None else sys.stderr
        self._platform_name = platform_name or sys.platform

    def inject(self, text: str) -> None:
        """Paste text into the active app, with clipboard fallback on failure.

        Parameters:
            text: Text payload to insert.

        Returns:
            None.

        Raises:
            RuntimeError: If running on non-macOS, or paste fails and fallback is disabled.

        Example:
            ``injector.inject("dictated sentence")``
        """

        if self._platform_name != "darwin":
            raise RuntimeError("Active-app output is only supported on macOS.")

        # Copy first so fallback still gives the user immediate manual paste.
        self._clipboard_injector.inject(text)

        try:
            self._paste_trigger()
        except Exception as exc:  # pragma: no cover - exercised via injected fakes.
            if not self._fallback_to_clipboard:
                raise RuntimeError(
                    "Active-app paste failed and clipboard fallback is disabled."
                ) from exc

            print(
                (
                    "flow-dictate: Active-app paste failed; text was copied to the clipboard "
                    "for manual paste."
                ),
                file=self._warning_stream,
            )
