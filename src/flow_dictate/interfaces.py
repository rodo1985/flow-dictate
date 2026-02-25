"""Core interfaces for dictation components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass(frozen=True, slots=True)
class AudioChunk:
    """Represent raw audio captured for one dictation segment.

    Parameters:
        data: Raw encoded bytes for the recording.
        sample_rate_hz: Sample rate in Hertz used to capture the audio.
        channels: Number of channels present in the recording.

    Returns:
        AudioChunk: Immutable audio payload metadata bundle.

    Raises:
        ValueError: If sample rate or channels are non-positive.

    Example:
        >>> AudioChunk(data=b"abc", sample_rate_hz=16_000, channels=1)
        AudioChunk(data=b'abc', sample_rate_hz=16000, channels=1)
    """

    data: bytes
    sample_rate_hz: int
    channels: int

    def __post_init__(self) -> None:
        """Validate audio metadata invariants.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            ValueError: If sample rate or channels are not positive integers.

        Example:
            >>> AudioChunk(data=b"x", sample_rate_hz=0, channels=1)
            Traceback (most recent call last):
                ...
            ValueError: sample_rate_hz must be greater than 0.
        """

        if self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be greater than 0.")
        if self.channels <= 0:
            raise ValueError("channels must be greater than 0.")


@dataclass(frozen=True, slots=True)
class InjectionResult:
    """Describe the outcome of one text-injection attempt.

    Parameters:
        inserted: Whether text was successfully inserted into the target destination.
        method: Injection method used (for example, ``stdout`` or ``direct-type``).
        fallback_used: Whether a fallback path was required.
        fallback_reason: Optional machine-readable fallback reason when ``fallback_used`` is ``True``.

    Returns:
        InjectionResult: Immutable text-injection outcome record.

    Raises:
        ValueError: If a fallback is marked as used without a non-empty reason.

    Example:
        >>> InjectionResult(
        ...     inserted=True,
        ...     method="direct-type",
        ...     fallback_used=True,
        ...     fallback_reason="direct_typing_failed",
        ... )
        InjectionResult(inserted=True, method='direct-type', fallback_used=True, fallback_reason='direct_typing_failed')
    """

    inserted: bool
    method: str
    fallback_used: bool = False
    fallback_reason: str | None = None

    def __post_init__(self) -> None:
        """Validate fallback invariants for telemetry safety.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            ValueError: If fallback metadata is inconsistent.

        Example:
            ``InjectionResult(inserted=True, method="stdout")``
        """

        if self.fallback_used and not (self.fallback_reason and self.fallback_reason.strip()):
            raise ValueError("fallback_reason must be provided when fallback_used is True.")


class HotkeyCapture(Protocol):
    """Define behavior for listening to a global hotkey trigger."""

    def wait_for_trigger(self, timeout_seconds: float | None = None) -> bool:
        """Wait for the configured hotkey and return whether it fired.

        Parameters:
            timeout_seconds: Optional timeout; ``None`` waits indefinitely.

        Returns:
            bool: ``True`` when hotkey was triggered, otherwise ``False``.

        Raises:
            RuntimeError: Implementations may raise for backend listener failures.

        Example:
            ``listener.wait_for_trigger(timeout_seconds=0.1)``
        """
        ...

    def is_pressed(self) -> bool:
        """Return whether the configured hotkey is currently held down.

        Parameters:
            None.

        Returns:
            bool: ``True`` when all required hotkey keys are actively pressed.

        Raises:
            RuntimeError: Implementations may raise for backend listener failures.

        Example:
            ``listener.is_pressed()``
        """
        ...


class AudioCapture(Protocol):
    """Define behavior for acquiring microphone audio data."""

    def record(self, max_seconds: float) -> AudioChunk:
        """Capture one audio segment up to the maximum duration.

        Parameters:
            max_seconds: Maximum capture duration in seconds.

        Returns:
            AudioChunk: Captured audio payload and metadata.

        Raises:
            RuntimeError: Implementations may raise for device or OS failures.

        Example:
            ``audio_capture.record(max_seconds=5.0)``
        """
        ...

    def record_while_pressed(
        self,
        is_pressed: Callable[[], bool],
        max_seconds: float,
        poll_interval_seconds: float = 0.01,
    ) -> AudioChunk:
        """Capture audio while a hotkey remains pressed.

        Parameters:
            is_pressed: Callable returning whether the hotkey is still held.
            max_seconds: Hard cap for one recording in seconds.
            poll_interval_seconds: Poll interval for checking key-release state.

        Returns:
            AudioChunk: Captured audio payload and metadata.

        Raises:
            RuntimeError: Implementations may raise for device or OS failures.

        Example:
            ``audio_capture.record_while_pressed(is_pressed=listener.is_pressed, max_seconds=30.0)``
        """
        ...


class TranscriptionClient(Protocol):
    """Define behavior for converting audio to text."""

    def transcribe(self, audio: AudioChunk) -> str:
        """Convert captured audio into text.

        Parameters:
            audio: Audio payload to transcribe.

        Returns:
            str: Recognized text, which may be an empty string.

        Raises:
            RuntimeError: Implementations may raise for API or decode failures.

        Example:
            ``client.transcribe(audio_chunk)``
        """
        ...


class TextInjector(Protocol):
    """Define behavior for injecting text into the active macOS target."""

    def inject(self, text: str) -> InjectionResult:
        """Insert text into the foreground application.

        Parameters:
            text: Final text to insert.

        Returns:
            InjectionResult: Structured insertion outcome for runtime telemetry.

        Raises:
            RuntimeError: Implementations may raise for accessibility failures.

        Example:
            ``injector.inject("hello world")``
        """
        ...
