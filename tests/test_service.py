"""Tests for dictation service orchestration behavior."""

from __future__ import annotations

from typing import Callable

from flow_dictate.config import AppConfig
from flow_dictate.interfaces import AudioChunk
from flow_dictate.service import DictationService


class SequenceHotkey:
    """Return a predetermined sequence of hotkey trigger events.

    Parameters:
        sequence: Ordered list of bool trigger outcomes for each wait call.

    Returns:
        SequenceHotkey: Deterministic hotkey fake for orchestration tests.

    Raises:
        None.

    Example:
        ``hotkey = SequenceHotkey([True, False])``
    """

    def __init__(self, sequence: list[bool]) -> None:
        """Store sequence values for deterministic reads.

        Parameters:
            sequence: Ordered trigger outcomes consumed one-by-one.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``SequenceHotkey([True])``
        """

        self._sequence = sequence

    def wait_for_trigger(self, timeout_seconds: float | None = None) -> bool:
        """Return the next trigger value, defaulting to ``False``.

        Parameters:
            timeout_seconds: Unused in this fake implementation.

        Returns:
            bool: Next pre-seeded value or ``False`` when exhausted.

        Raises:
            None.

        Example:
            ``hotkey.wait_for_trigger(timeout_seconds=0.0)``
        """

        if self._sequence:
            return self._sequence.pop(0)
        return False


class FakeAudioCapture:
    """Collect requested recording durations and return fixed audio data.

    Parameters:
        None.

    Returns:
        FakeAudioCapture: Recording fake with call tracking.

    Raises:
        None.

    Example:
        ``audio = FakeAudioCapture()``
    """

    def __init__(self) -> None:
        """Initialize call tracking state.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``FakeAudioCapture()``
        """

        self.record_calls: list[float] = []

    def record(self, max_seconds: float) -> AudioChunk:
        """Track requested duration and return a fixed audio chunk.

        Parameters:
            max_seconds: Max recording duration requested by the orchestrator.

        Returns:
            AudioChunk: Synthetic payload for tests.

        Raises:
            None.

        Example:
            ``audio.record(max_seconds=30.0)``
        """

        self.record_calls.append(max_seconds)
        return AudioChunk(data=b"audio", sample_rate_hz=16_000, channels=1)


class FakeTranscriptionClient:
    """Return a preset transcription string."""

    def __init__(self, text: str) -> None:
        """Initialize fake with fixed transcription output.

        Parameters:
            text: Text returned for every transcription call.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``FakeTranscriptionClient("hello")``
        """

        self._text = text

    def transcribe(self, audio: AudioChunk) -> str:
        """Return the configured transcription output.

        Parameters:
            audio: Captured audio payload; unused by this fake.

        Returns:
            str: Preset text.

        Raises:
            None.

        Example:
            ``client.transcribe(audio_chunk)``
        """

        return self._text


class FakeTextInjector:
    """Collect injected text values for assertions."""

    def __init__(self) -> None:
        """Initialize injection history storage.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``injector = FakeTextInjector()``
        """

        self.injected_text: list[str] = []

    def inject(self, text: str) -> None:
        """Append text to in-memory history.

        Parameters:
            text: Text requested for injection.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``injector.inject("hello")``
        """

        self.injected_text.append(text)


def test_run_once_injects_text_after_trigger() -> None:
    """Verify full pipeline runs when a hotkey trigger is present.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If orchestration order or outputs are incorrect.

    Example:
        ``pytest -k test_run_once_injects_text_after_trigger``
    """

    config = AppConfig(max_record_seconds=12.5)
    hotkey = SequenceHotkey([True])
    audio = FakeAudioCapture()
    transcription = FakeTranscriptionClient("hello world")
    injector = FakeTextInjector()

    service = DictationService(
        config=config,
        hotkey_capture=hotkey,
        audio_capture=audio,
        transcription_client=transcription,
        text_injector=injector,
    )

    result = service.run_once(timeout_seconds=0.0)

    assert result.triggered is True
    assert result.transcription == "hello world"
    assert result.injected is True
    assert audio.record_calls == [12.5]
    assert injector.injected_text == ["hello world"]


def test_run_once_skips_injection_for_blank_transcription() -> None:
    """Verify blank transcriptions do not get injected into target applications.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If blank transcript handling regresses.

    Example:
        ``pytest -k test_run_once_skips_injection_for_blank_transcription``
    """

    service = DictationService(
        config=AppConfig(),
        hotkey_capture=SequenceHotkey([True]),
        audio_capture=FakeAudioCapture(),
        transcription_client=FakeTranscriptionClient("   "),
        text_injector=FakeTextInjector(),
    )

    result = service.run_once(timeout_seconds=0.0)

    assert result.triggered is True
    assert result.transcription == ""
    assert result.injected is False


class HoldAwareHotkey:
    """Provide trigger and held-state behavior for hold-to-record tests.

    Parameters:
        held_sequence: Ordered held-state values consumed during polling.

    Returns:
        HoldAwareHotkey: Fake hotkey with deterministic hold semantics.

    Raises:
        None.

    Example:
        ``hotkey = HoldAwareHotkey([True, False])``
    """

    def __init__(self, held_sequence: list[bool]) -> None:
        """Store held-state values for deterministic reads.

        Parameters:
            held_sequence: Ordered held-state values consumed one-by-one.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``HoldAwareHotkey([True, False])``
        """

        self._held_sequence = held_sequence

    def wait_for_trigger(self, timeout_seconds: float | None = None) -> bool:
        """Always report a trigger for one-cycle hold-mode tests.

        Parameters:
            timeout_seconds: Unused in this fake implementation.

        Returns:
            bool: Always ``True``.

        Raises:
            None.

        Example:
            ``hotkey.wait_for_trigger(timeout_seconds=0.0)``
        """

        return True

    def is_pressed(self) -> bool:
        """Return the next held-state value, defaulting to ``False``.

        Parameters:
            None.

        Returns:
            bool: Next pre-seeded held value or ``False`` when exhausted.

        Raises:
            None.

        Example:
            ``hotkey.is_pressed()``
        """

        if self._held_sequence:
            return self._held_sequence.pop(0)
        return False


class HoldAwareAudioCapture:
    """Provide record-while-pressed behavior for service hold-mode tests.

    Parameters:
        None.

    Returns:
        HoldAwareAudioCapture: Fake capture implementation with call tracking.

    Raises:
        None.

    Example:
        ``audio = HoldAwareAudioCapture()``
    """

    def __init__(self) -> None:
        """Initialize call tracking state for record methods.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``HoldAwareAudioCapture()``
        """

        self.record_called = False
        self.record_while_pressed_called = False

    def record(self, max_seconds: float) -> AudioChunk:
        """Track legacy record usage and return deterministic payload.

        Parameters:
            max_seconds: Max recording duration requested by the service.

        Returns:
            AudioChunk: Fixed deterministic payload.

        Raises:
            None.

        Example:
            ``audio.record(max_seconds=5.0)``
        """

        del max_seconds
        self.record_called = True
        return AudioChunk(data=b"legacy", sample_rate_hz=24_000, channels=1)

    def record_while_pressed(
        self,
        is_pressed: Callable[[], bool],
        max_seconds: float,
        poll_interval_seconds: float = 0.01,
    ) -> AudioChunk:
        """Track hold-mode usage and return deterministic payload.

        Parameters:
            is_pressed: Callable returning whether recording should continue.
            max_seconds: Max recording duration requested by the service.
            poll_interval_seconds: Poll interval from the service; unused here.

        Returns:
            AudioChunk: Fixed deterministic payload.

        Raises:
            None.

        Example:
            ``audio.record_while_pressed(is_pressed=hotkey.is_pressed, max_seconds=5.0)``
        """

        del max_seconds, poll_interval_seconds
        self.record_while_pressed_called = True
        _ = is_pressed()
        _ = is_pressed()
        return AudioChunk(data=b"hold-mode", sample_rate_hz=24_000, channels=1)


def test_run_once_prefers_hold_to_record_path_when_available() -> None:
    """Verify service uses ``record_while_pressed`` when capture supports it.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If hold-mode path selection regresses.

    Example:
        ``pytest -k test_run_once_prefers_hold_to_record_path_when_available``
    """

    audio = HoldAwareAudioCapture()
    service = DictationService(
        config=AppConfig(),
        hotkey_capture=HoldAwareHotkey([True, False]),
        audio_capture=audio,
        transcription_client=FakeTranscriptionClient("hold transcript"),
        text_injector=FakeTextInjector(),
    )

    result = service.run_once(timeout_seconds=0.0)

    assert result.triggered is True
    assert result.transcription == "hold transcript"
    assert result.injected is True
    assert audio.record_called is False
    assert audio.record_while_pressed_called is True


def test_run_once_emits_recording_callbacks() -> None:
    """Verify recording start/stop callbacks are fired for one run cycle.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If callback invocation behavior regresses.

    Example:
        ``pytest -k test_run_once_emits_recording_callbacks``
    """

    events: list[str] = []
    service = DictationService(
        config=AppConfig(),
        hotkey_capture=HoldAwareHotkey([True, False]),
        audio_capture=HoldAwareAudioCapture(),
        transcription_client=FakeTranscriptionClient("hello"),
        text_injector=FakeTextInjector(),
        on_recording_started=lambda: events.append("start"),
        on_recording_stopped=lambda elapsed: events.append(
            "stop" if elapsed >= 0 else "bad-stop"
        ),
    )

    service.run_once(timeout_seconds=0.0)

    assert events[0] == "start"
    assert "stop" in events
