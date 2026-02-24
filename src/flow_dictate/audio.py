"""Audio capture stubs for scaffolding and offline tests."""

from __future__ import annotations

from flow_dictate.interfaces import AudioCapture, AudioChunk


class StubAudioCapture(AudioCapture):
    """Return deterministic placeholder audio bytes instead of microphone input.

    Parameters:
        sample_rate_hz: Sample rate metadata assigned to emitted chunks.
        channels: Number of channels metadata assigned to emitted chunks.

    Returns:
        StubAudioCapture: Deterministic audio-capture stub.

    Raises:
        ValueError: If sample rate or channels are non-positive.

    Example:
        >>> capture = StubAudioCapture(sample_rate_hz=16_000, channels=1)
        >>> chunk = capture.record(max_seconds=1.0)
        >>> bool(chunk.data)
        True
    """

    def __init__(self, sample_rate_hz: int = 16_000, channels: int = 1) -> None:
        """Initialize stub capture metadata.

        Parameters:
            sample_rate_hz: Sample rate metadata assigned to output chunks.
            channels: Number of channels metadata assigned to output chunks.

        Returns:
            None.

        Raises:
            ValueError: If sample rate or channels are non-positive.

        Example:
            ``StubAudioCapture(sample_rate_hz=16000, channels=1)``
        """

        if sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be greater than 0.")
        if channels <= 0:
            raise ValueError("channels must be greater than 0.")

        self._sample_rate_hz = sample_rate_hz
        self._channels = channels

    def record(self, max_seconds: float) -> AudioChunk:
        """Generate deterministic placeholder bytes for a requested duration.

        Parameters:
            max_seconds: Maximum capture duration requested by the caller.

        Returns:
            AudioChunk: Deterministic pseudo-audio data with configured metadata.

        Raises:
            ValueError: If ``max_seconds`` is non-positive.

        Example:
            ``capture.record(max_seconds=2.0)``
        """

        if max_seconds <= 0:
            raise ValueError("max_seconds must be greater than 0.")

        # Use duration to vary payload size so tests can assert the right value flowed through.
        payload_size = max(1, int(max_seconds * 10))
        payload = b"\x00" * payload_size

        return AudioChunk(
            data=payload,
            sample_rate_hz=self._sample_rate_hz,
            channels=self._channels,
        )
