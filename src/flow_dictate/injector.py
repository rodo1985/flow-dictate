"""Text injection implementations for stdout, clipboard, and active macOS app insertion."""

from __future__ import annotations

import subprocess
import sys
from typing import Callable, TextIO

from flow_dictate.config import VALID_ACTIVE_APP_INSERTION_STRATEGIES
from flow_dictate.interfaces import InjectionResult, TextInjector


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


def _run_osascript(arguments: list[str], purpose: str) -> None:
    """Run ``osascript`` with explicit arguments and normalize errors.

    Parameters:
        arguments: Full argument vector to pass to ``osascript``.
        purpose: Human-readable operation description used in error messages.

    Returns:
        None.

    Raises:
        RuntimeError: If ``osascript`` is unavailable or returns a non-zero exit code.

    Example:
        ``_run_osascript(["osascript", "-e", "display dialog \"hi\""], "dialog")``
    """

    try:
        process = subprocess.run(
            arguments,
            check=False,
            text=True,
            capture_output=True,
        )
    except OSError as exc:
        raise RuntimeError(f"Unable to run osascript for {purpose}.") from exc

    if process.returncode != 0:
        stderr_output = process.stderr.strip()
        raise RuntimeError(
            f"osascript command failed during {purpose}: {stderr_output or 'unknown error'}"
        )


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
    _run_osascript(["osascript", "-e", paste_script], purpose="active-app paste")


def _trigger_active_app_direct_typing_with_osascript(text: str) -> None:
    """Type plain text into the active app using AppleScript keystrokes.

    Parameters:
        text: Text payload to type into the active application.

    Returns:
        None.

    Raises:
        RuntimeError: If direct typing automation fails.

    Example:
        ``_trigger_active_app_direct_typing_with_osascript("hello world")``
    """

    _run_osascript(
        [
            "osascript",
            "-e",
            "on run argv",
            "-e",
            'tell application "System Events" to keystroke (item 1 of argv)',
            "-e",
            "end run",
            text,
        ],
        purpose="direct typing",
    )


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

    def inject(self, text: str) -> InjectionResult:
        """Emit text to the configured stream.

        Parameters:
            text: Text payload to emit.

        Returns:
            InjectionResult: Structured insertion outcome for telemetry use.

        Raises:
            None.

        Example:
            ``injector.inject("transcribed text")``
        """

        print(text, file=self._stream)
        return InjectionResult(inserted=True, method="stdout")


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

    def inject(self, text: str) -> InjectionResult:
        """Write text to the clipboard.

        Parameters:
            text: Text payload to copy.

        Returns:
            InjectionResult: Structured insertion outcome for telemetry use.

        Raises:
            RuntimeError: If clipboard write fails.

        Example:
            ``injector.inject("copy me")``
        """

        self._clipboard_writer(text)
        return InjectionResult(inserted=True, method="clipboard")


class MacOSActiveAppTextInjector(TextInjector):
    """Insert text into the active macOS app with strategy-aware fallback behavior.

    Parameters:
        clipboard_injector: Clipboard injector used to stage text for paste.
        paste_trigger: Callable that triggers the active-app paste action.
        direct_typing_trigger: Callable that types plain text into the active app.
        insertion_strategy: Primary active-app insertion strategy.
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
        direct_typing_trigger: Callable[[str], None] | None = None,
        insertion_strategy: str = "clipboard-paste",
        fallback_to_clipboard: bool = True,
        warning_stream: TextIO | None = None,
        platform_name: str | None = None,
    ) -> None:
        """Initialize active-app insertion dependencies.

        Parameters:
            clipboard_injector: Injector used to copy text into clipboard.
            paste_trigger: Function that performs active-app paste.
            direct_typing_trigger: Function that types text in active app.
            insertion_strategy: Preferred active-app insertion strategy.
            fallback_to_clipboard: Whether to suppress paste errors and keep clipboard content.
            warning_stream: Stream for warning messages on fallback.
            platform_name: Optional platform override used by tests.

        Returns:
            ValueError: If ``insertion_strategy`` is unsupported.

        Raises:
            None.

        Example:
            ``MacOSActiveAppTextInjector(fallback_to_clipboard=False)``
        """

        if insertion_strategy not in VALID_ACTIVE_APP_INSERTION_STRATEGIES:
            valid_strategies = ", ".join(VALID_ACTIVE_APP_INSERTION_STRATEGIES)
            raise ValueError(
                f"insertion_strategy must be one of: {valid_strategies}."
            )

        self._clipboard_injector = clipboard_injector or ClipboardTextInjector()
        self._paste_trigger = paste_trigger or _trigger_active_app_paste_with_osascript
        self._direct_typing_trigger = (
            direct_typing_trigger or _trigger_active_app_direct_typing_with_osascript
        )
        self._insertion_strategy = insertion_strategy
        self._fallback_to_clipboard = fallback_to_clipboard
        self._warning_stream = warning_stream if warning_stream is not None else sys.stderr
        self._platform_name = platform_name or sys.platform

    def _inject_via_clipboard_paste(self, text: str) -> InjectionResult:
        """Insert text by staging clipboard data and triggering Command+V.

        Parameters:
            text: Text payload to insert.

        Returns:
            InjectionResult: Structured insertion outcome.

        Raises:
            RuntimeError: If paste fails and fallback is disabled.

        Example:
            ``self._inject_via_clipboard_paste("dictated sentence")``
        """

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
            return InjectionResult(
                inserted=True,
                method="clipboard-paste",
                fallback_used=True,
                fallback_reason="paste_trigger_failed",
            )

        return InjectionResult(inserted=True, method="clipboard-paste")

    def _inject_via_direct_typing(self, text: str) -> InjectionResult:
        """Insert text by typing into the active app, with clipboard+paste fallback.

        Parameters:
            text: Text payload to insert.

        Returns:
            InjectionResult: Structured insertion outcome.

        Raises:
            RuntimeError: If direct typing fails and fallback is disabled.

        Example:
            ``self._inject_via_direct_typing("hello")``
        """

        try:
            self._direct_typing_trigger(text)
        except Exception as exc:  # pragma: no cover - exercised via injected fakes.
            if not self._fallback_to_clipboard:
                raise RuntimeError(
                    "Direct typing failed and clipboard fallback is disabled."
                ) from exc

            # We intentionally fallback to paste so users still get near-automatic insertion
            # even when a target app blocks synthetic key typing events.
            fallback_result = self._inject_via_clipboard_paste(text=text)
            print(
                (
                    "flow-dictate: Direct typing failed; used clipboard fallback path "
                    "for active-app insertion."
                ),
                file=self._warning_stream,
            )
            return InjectionResult(
                inserted=fallback_result.inserted,
                method="direct-type",
                fallback_used=True,
                fallback_reason="direct_typing_failed",
            )

        return InjectionResult(inserted=True, method="direct-type")

    def inject(self, text: str) -> InjectionResult:
        """Insert text into the active app using the configured strategy.

        Parameters:
            text: Text payload to insert.

        Returns:
            InjectionResult: Structured insertion outcome for telemetry use.

        Raises:
            RuntimeError: If running on non-macOS or insertion fails without fallback.

        Example:
            ``injector.inject("dictated sentence")``
        """

        if self._platform_name != "darwin":
            raise RuntimeError("Active-app output is only supported on macOS.")

        if self._insertion_strategy == "clipboard-paste":
            return self._inject_via_clipboard_paste(text=text)

        return self._inject_via_direct_typing(text=text)
