"""Audio capture backends for scaffolding and real microphone recording."""

from __future__ import annotations

import time
from typing import Callable
from typing import Any

import numpy as np

from flow_dictate.interfaces import AudioCapture, AudioChunk


def _import_sounddevice() -> Any:
    """Import ``sounddevice`` lazily to keep test and stub paths lightweight.

    Parameters:
        None.

    Returns:
        Any: Imported ``sounddevice`` module.

    Raises:
        RuntimeError: If the optional ``sounddevice`` dependency is missing.

    Example:
        ``sounddevice = _import_sounddevice()``
    """

    try:
        import sounddevice  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Real microphone capture requires the 'sounddevice' package. "
            "Install dependencies with `uv sync`."
        ) from exc

    return sounddevice


def _normalize_audio_device(device: str | int | None) -> str | int | None:
    """Normalize audio device identifiers for ``sounddevice`` calls.

    Parameters:
        device: Optional device id/name from configuration.

    Returns:
        str | int | None: Integer index when a numeric string is supplied,
        otherwise the original string or ``None``.

    Raises:
        None.

    Example:
        >>> _normalize_audio_device("2")
        2
    """

    if device is None:
        return None
    if isinstance(device, int):
        return device
    if device.isdigit():
        return int(device)
    return device


def _to_mono_pcm16_bytes(raw_frames: np.ndarray) -> bytes:
    """Convert captured audio frames to mono PCM16 bytes.

    Parameters:
        raw_frames: Numpy array returned by ``sounddevice.rec``.

    Returns:
        bytes: Little-endian PCM16 byte payload.

    Raises:
        RuntimeError: If frame dimensions are unsupported.

    Example:
        ``payload = _to_mono_pcm16_bytes(frames)``
    """

    if raw_frames.ndim == 1:
        mono_frames = raw_frames
    elif raw_frames.ndim == 2 and raw_frames.shape[1] == 1:
        mono_frames = raw_frames[:, 0]
    elif raw_frames.ndim == 2:
        # We intentionally average channels because the realtime backend expects
        # mono PCM and this keeps behavior predictable across hardware.
        mono_float = raw_frames.astype(np.float32).mean(axis=1)
        mono_float = np.clip(mono_float, -32768, 32767)
        mono_frames = mono_float.astype(np.int16)
    else:
        raise RuntimeError("Unsupported microphone frame shape returned by sounddevice.")

    return mono_frames.astype(np.int16).tobytes()


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
        >>> capture = StubAudioCapture(sample_rate_hz=24_000, channels=1)
        >>> chunk = capture.record(max_seconds=1.0)
        >>> bool(chunk.data)
        True
    """

    def __init__(self, sample_rate_hz: int = 24_000, channels: int = 1) -> None:
        """Initialize stub capture metadata.

        Parameters:
            sample_rate_hz: Sample rate metadata assigned to output chunks.
            channels: Number of channels metadata assigned to output chunks.

        Returns:
            None.

        Raises:
            ValueError: If sample rate or channels are non-positive.

        Example:
            ``StubAudioCapture(sample_rate_hz=24000, channels=1)``
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

    def record_while_pressed(
        self,
        is_pressed: Callable[[], bool],
        max_seconds: float,
        poll_interval_seconds: float = 0.01,
    ) -> AudioChunk:
        """Generate deterministic placeholder bytes while hotkey remains pressed.

        Parameters:
            is_pressed: Callable returning whether recording should continue.
            max_seconds: Maximum simulated capture duration in seconds.
            poll_interval_seconds: Poll delay for checking key state.

        Returns:
            AudioChunk: Deterministic pseudo-audio data with configured metadata.

        Raises:
            ValueError: If duration or poll interval is non-positive.

        Example:
            ``capture.record_while_pressed(is_pressed=lambda: True, max_seconds=1.0)``
        """

        if max_seconds <= 0:
            raise ValueError("max_seconds must be greater than 0.")
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be greater than 0.")

        if not is_pressed():
            return AudioChunk(
                data=b"",
                sample_rate_hz=self._sample_rate_hz,
                channels=self._channels,
            )

        started_monotonic = time.monotonic()
        while is_pressed() and (time.monotonic() - started_monotonic) < max_seconds:
            remaining = max_seconds - (time.monotonic() - started_monotonic)
            time.sleep(min(poll_interval_seconds, max(0.0, remaining)))

        elapsed_seconds = min(
            max_seconds,
            max(0.0, time.monotonic() - started_monotonic),
        )
        payload_size = max(1, int(elapsed_seconds * 10))
        payload = b"\x00" * payload_size

        return AudioChunk(
            data=payload,
            sample_rate_hz=self._sample_rate_hz,
            channels=self._channels,
        )


class MicrophoneAudioCapture(AudioCapture):
    """Capture real microphone input using ``sounddevice``.

    Parameters:
        sample_rate_hz: Requested sample rate in Hertz.
        channels: Number of channels to capture from the microphone input.
        device: Optional device id or device name accepted by ``sounddevice``.

    Returns:
        MicrophoneAudioCapture: Real audio capture backend.

    Raises:
        ValueError: If sample rate or channels are non-positive.

    Example:
        ``capture = MicrophoneAudioCapture(sample_rate_hz=24000, channels=1)``
    """

    def __init__(
        self,
        sample_rate_hz: int = 24_000,
        channels: int = 1,
        device: str | int | None = None,
    ) -> None:
        """Initialize microphone capture configuration.

        Parameters:
            sample_rate_hz: Requested sample rate in Hertz.
            channels: Number of channels to capture.
            device: Optional device id or name.

        Returns:
            None.

        Raises:
            ValueError: If sample rate or channels are non-positive.

        Example:
            ``MicrophoneAudioCapture(sample_rate_hz=24000, channels=1, device=None)``
        """

        if sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be greater than 0.")
        if channels <= 0:
            raise ValueError("channels must be greater than 0.")

        self._sample_rate_hz = sample_rate_hz
        self._channels = channels
        self._device = _normalize_audio_device(device)

    def record(self, max_seconds: float) -> AudioChunk:
        """Record microphone input for up to ``max_seconds`` seconds.

        Parameters:
            max_seconds: Maximum audio capture duration in seconds.

        Returns:
            AudioChunk: Captured mono PCM16 audio bytes.

        Raises:
            ValueError: If ``max_seconds`` is non-positive.
            RuntimeError: If the recording backend fails or records no frames.

        Example:
            ``chunk = capture.record(max_seconds=5.0)``
        """

        if max_seconds <= 0:
            raise ValueError("max_seconds must be greater than 0.")

        frame_count = int(self._sample_rate_hz * max_seconds)
        if frame_count <= 0:
            raise ValueError("max_seconds is too small for the configured sample rate.")

        sounddevice = _import_sounddevice()
        try:
            raw_frames = sounddevice.rec(
                frames=frame_count,
                samplerate=self._sample_rate_hz,
                channels=self._channels,
                dtype="int16",
                device=self._device,
            )
            sounddevice.wait()
        except Exception as exc:
            raise RuntimeError("Failed to capture audio from the microphone.") from exc

        payload = _to_mono_pcm16_bytes(raw_frames)
        if not payload:
            raise RuntimeError("Microphone capture returned an empty audio payload.")

        return AudioChunk(
            data=payload,
            sample_rate_hz=self._sample_rate_hz,
            channels=1,
        )

    def record_while_pressed(
        self,
        is_pressed: Callable[[], bool],
        max_seconds: float,
        poll_interval_seconds: float = 0.01,
    ) -> AudioChunk:
        """Record audio while the hotkey remains pressed.

        Parameters:
            is_pressed: Callable returning whether recording should continue.
            max_seconds: Maximum audio capture duration in seconds.
            poll_interval_seconds: Poll delay for checking key-release state.

        Returns:
            AudioChunk: Captured mono PCM16 audio bytes.

        Raises:
            ValueError: If ``max_seconds`` or ``poll_interval_seconds`` is non-positive.
            RuntimeError: If microphone stream setup or capture fails.

        Example:
            ``chunk = capture.record_while_pressed(is_pressed=listener.is_pressed, max_seconds=30.0)``
        """

        if max_seconds <= 0:
            raise ValueError("max_seconds must be greater than 0.")
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be greater than 0.")

        if not is_pressed():
            return AudioChunk(
                data=b"",
                sample_rate_hz=self._sample_rate_hz,
                channels=1,
            )

        sounddevice = _import_sounddevice()
        captured_frames: list[np.ndarray] = []

        def _on_audio_frame(
            indata: np.ndarray,
            frames: int,
            time_info: Any,
            status: Any,
        ) -> None:
            """Collect streaming microphone frames from sounddevice callbacks.

            Parameters:
                indata: Incoming audio frame block.
                frames: Frame count in ``indata``.
                time_info: Callback timing metadata from sounddevice.
                status: Stream status metadata from sounddevice.

            Returns:
                None.

            Raises:
                None.

            Example:
                Internal callback only.
            """

            del frames, time_info, status
            captured_frames.append(indata.copy())

        try:
            with sounddevice.InputStream(
                samplerate=self._sample_rate_hz,
                channels=self._channels,
                dtype="int16",
                device=self._device,
                callback=_on_audio_frame,
            ):
                started_monotonic = time.monotonic()
                while is_pressed() and (time.monotonic() - started_monotonic) < max_seconds:
                    remaining = max_seconds - (time.monotonic() - started_monotonic)
                    time.sleep(min(poll_interval_seconds, max(0.0, remaining)))
        except Exception as exc:
            raise RuntimeError("Failed to capture streaming audio from the microphone.") from exc

        if not captured_frames:
            return AudioChunk(
                data=b"",
                sample_rate_hz=self._sample_rate_hz,
                channels=1,
            )

        concatenated_frames = np.concatenate(captured_frames, axis=0)
        payload = _to_mono_pcm16_bytes(concatenated_frames)

        return AudioChunk(
            data=payload,
            sample_rate_hz=self._sample_rate_hz,
            channels=1,
        )
