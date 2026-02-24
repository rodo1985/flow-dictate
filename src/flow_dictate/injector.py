"""Text injection stubs for local development."""

from __future__ import annotations

import sys
from typing import TextIO

from flow_dictate.interfaces import TextInjector


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
