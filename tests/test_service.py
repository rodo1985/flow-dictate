"""Tests for dictation service orchestration behavior."""

from __future__ import annotations

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
