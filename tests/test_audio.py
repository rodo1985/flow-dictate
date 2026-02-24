"""Tests for real microphone capture helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

import flow_dictate.audio as audio_module
from flow_dictate.audio import MicrophoneAudioCapture


@dataclass
class _FakeSoundDevice:
    """Lightweight fake for the ``sounddevice`` module used in tests.

    Parameters:
        response_frames: Numpy frames returned from ``rec``.

    Returns:
        _FakeSoundDevice: Fake module object.

    Raises:
        None.

    Example:
        ``fake = _FakeSoundDevice(response_frames=np.zeros((2, 2), dtype=np.int16))``
    """

    response_frames: np.ndarray

    def __post_init__(self) -> None:
        """Initialize call tracking state.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``fake.__post_init__()``
        """

        self.last_rec_kwargs: dict[str, Any] = {}
        self.wait_called = False

    def rec(self, **kwargs: Any) -> np.ndarray:
        """Capture ``rec`` call kwargs and return canned frames.

        Parameters:
            **kwargs: Recording options passed by ``MicrophoneAudioCapture``.

        Returns:
            np.ndarray: Pre-configured frame array.

        Raises:
            None.

        Example:
            ``frames = fake.rec(frames=24, samplerate=24000, channels=2, dtype="int16")``
        """

        self.last_rec_kwargs = kwargs
        return self.response_frames

    def wait(self) -> None:
        """Mark ``wait`` as called.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``fake.wait()``
        """

        self.wait_called = True


def test_microphone_capture_downmixes_stereo_frames(monkeypatch: Any) -> None:
    """Verify real capture path downmixes stereo frames to mono PCM16 bytes.

    Parameters:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        AssertionError: If downmixing or sounddevice calls regress.

    Example:
        ``pytest -k test_microphone_capture_downmixes_stereo_frames``
    """

    fake_sounddevice = _FakeSoundDevice(
        response_frames=np.array([[1000, -1000], [2000, -2000]], dtype=np.int16)
    )
    monkeypatch.setattr(audio_module, "_import_sounddevice", lambda: fake_sounddevice)

    capture = MicrophoneAudioCapture(sample_rate_hz=24_000, channels=2, device="3")
    chunk = capture.record(max_seconds=0.01)

    assert chunk.sample_rate_hz == 24_000
    assert chunk.channels == 1
    assert chunk.data == b"\x00\x00\x00\x00"
    assert fake_sounddevice.wait_called is True
    assert fake_sounddevice.last_rec_kwargs["device"] == 3
    assert fake_sounddevice.last_rec_kwargs["dtype"] == "int16"


def test_microphone_capture_validates_duration() -> None:
    """Verify non-positive recording durations are rejected.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If validation does not raise.

    Example:
        ``pytest -k test_microphone_capture_validates_duration``
    """

    capture = MicrophoneAudioCapture(sample_rate_hz=24_000, channels=1)

    try:
        capture.record(max_seconds=0.0)
    except ValueError as exc:
        assert "max_seconds" in str(exc)
    else:
        raise AssertionError("Expected ValueError for max_seconds=0.0")
