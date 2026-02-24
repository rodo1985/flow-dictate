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


class _FakeStreamingSoundDevice:
    """Lightweight fake for ``sounddevice.InputStream`` based capture tests.

    Parameters:
        callback_frames: Frames emitted to the stream callback on enter.

    Returns:
        _FakeStreamingSoundDevice: Fake module object.

    Raises:
        None.

    Example:
        ``fake = _FakeStreamingSoundDevice(np.array([[100]], dtype=np.int16))``
    """

    def __init__(self, callback_frames: np.ndarray) -> None:
        """Store callback frame payload and initialize call tracking.

        Parameters:
            callback_frames: Frames that should be passed to the callback.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``_FakeStreamingSoundDevice(np.zeros((1, 1), dtype=np.int16))``
        """

        self.callback_frames = callback_frames
        self.input_stream_kwargs: dict[str, Any] = {}

    class _InputStreamContext:
        """Context manager that triggers one callback invocation.

        Parameters:
            owner: Parent fake sounddevice module.
            kwargs: Stream kwargs used to configure callbacks and device settings.

        Returns:
            _InputStreamContext: Fake stream context manager.

        Raises:
            None.

        Example:
            ``ctx = _InputStreamContext(owner=fake, kwargs={...})``
        """

        def __init__(self, owner: "_FakeStreamingSoundDevice", kwargs: dict[str, Any]) -> None:
            """Store parent fake and stream configuration.

            Parameters:
                owner: Parent fake sounddevice module.
                kwargs: Stream kwargs used for callback invocation.

            Returns:
                None.

            Raises:
                None.

            Example:
                ``_InputStreamContext(owner=fake, kwargs={"channels": 1})``
            """

            self._owner = owner
            self._kwargs = kwargs

        def __enter__(self) -> "_FakeStreamingSoundDevice._InputStreamContext":
            """Emit one callback frame block upon stream open.

            Parameters:
                None.

            Returns:
                _InputStreamContext: This context manager instance.

            Raises:
                None.

            Example:
                Internal context manager callback.
            """

            callback = self._kwargs["callback"]
            callback(self._owner.callback_frames, self._owner.callback_frames.shape[0], None, None)
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            """Allow exceptions to propagate normally.

            Parameters:
                exc_type: Exception type from context block.
                exc: Exception instance from context block.
                tb: Traceback from context block.

            Returns:
                bool: Always ``False`` to propagate exceptions.

            Raises:
                None.

            Example:
                Internal context manager callback.
            """

            del exc_type, exc, tb
            return False

    def InputStream(self, **kwargs: Any) -> "_FakeStreamingSoundDevice._InputStreamContext":
        """Capture stream kwargs and return fake stream context manager.

        Parameters:
            **kwargs: Stream options passed by ``MicrophoneAudioCapture``.

        Returns:
            _InputStreamContext: Fake context manager that emits callback frames.

        Raises:
            None.

        Example:
            ``stream = fake.InputStream(samplerate=24000, channels=1, callback=cb)``
        """

        self.input_stream_kwargs = kwargs
        return self._InputStreamContext(owner=self, kwargs=kwargs)


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


def test_microphone_capture_record_while_pressed_uses_streaming_input(
    monkeypatch: Any,
) -> None:
    """Verify hold-mode capture records frames from ``InputStream`` callbacks.

    Parameters:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        AssertionError: If streaming capture behavior regresses.

    Example:
        ``pytest -k test_microphone_capture_record_while_pressed_uses_streaming_input``
    """

    fake_streaming_sounddevice = _FakeStreamingSoundDevice(
        callback_frames=np.array([[100], [200]], dtype=np.int16)
    )
    monkeypatch.setattr(
        audio_module,
        "_import_sounddevice",
        lambda: fake_streaming_sounddevice,
    )

    capture = MicrophoneAudioCapture(sample_rate_hz=24_000, channels=1, device="4")
    press_states = iter([True, False])
    chunk = capture.record_while_pressed(
        is_pressed=lambda: next(press_states, False),
        max_seconds=1.0,
        poll_interval_seconds=0.001,
    )

    assert chunk.sample_rate_hz == 24_000
    assert chunk.channels == 1
    assert chunk.data == (100).to_bytes(2, "little", signed=True) + (200).to_bytes(
        2,
        "little",
        signed=True,
    )
    assert fake_streaming_sounddevice.input_stream_kwargs["device"] == 4
