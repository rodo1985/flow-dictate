"""Service orchestration for flow-dictate."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable

from flow_dictate.config import AppConfig
from flow_dictate.interfaces import (
    AudioCapture,
    AudioChunk,
    HotkeyCapture,
    InjectionResult,
    TextInjector,
    TranscriptionClient,
)


@dataclass(frozen=True, slots=True)
class ServiceRunResult:
    """Summarize one iteration of the dictation service loop.

    Parameters:
        triggered: Whether a hotkey trigger was observed.
        transcription: Text produced by transcription, if any.
        injected: Whether text was sent to the injector.
        injection_result: Structured injector outcome when injection was attempted.

    Returns:
        ServiceRunResult: Immutable summary of one orchestrator cycle.

    Raises:
        None.

    Example:
        >>> ServiceRunResult(triggered=True, transcription="hello", injected=True)
        ServiceRunResult(triggered=True, transcription='hello', injected=True)
    """

    triggered: bool
    transcription: str | None
    injected: bool
    injection_result: InjectionResult | None = None


class DictationService:
    """Coordinate hotkey, audio, transcription, and text injection components.

    Parameters:
        config: Runtime configuration for durations and polling.
        hotkey_capture: Backend component that waits for hotkey events.
        audio_capture: Backend component that records microphone data.
        transcription_client: Backend component that converts audio to text.
        text_injector: Backend component that inserts text into target app.

    Returns:
        DictationService: Ready-to-run service orchestrator.

    Raises:
        None.

    Example:
        ``service = DictationService(config, hotkey, audio, transcriber, injector)``
    """

    def __init__(
        self,
        config: AppConfig,
        hotkey_capture: HotkeyCapture,
        audio_capture: AudioCapture,
        transcription_client: TranscriptionClient,
        text_injector: TextInjector,
        on_recording_started: Callable[[], None] | None = None,
        on_recording_stopped: Callable[[float], None] | None = None,
        on_transcription_started: Callable[[], None] | None = None,
        on_transcription_completed: Callable[[str], None] | None = None,
        on_injection_completed: Callable[[InjectionResult], None] | None = None,
    ) -> None:
        """Store orchestration dependencies.

        Parameters:
            config: Runtime configuration object.
            hotkey_capture: Trigger listener implementation.
            audio_capture: Audio capture implementation.
            transcription_client: Audio-to-text implementation.
            text_injector: Text injection implementation.
            on_recording_started: Optional callback fired right before recording begins.
            on_recording_stopped: Optional callback fired after recording stops with duration.
            on_transcription_started: Optional callback fired before transcription starts.
            on_transcription_completed: Optional callback fired after transcription completes.
            on_injection_completed: Optional callback fired after insertion completes.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``DictationService(config, hotkey, audio, client, injector)``
        """

        self._config = config
        self._hotkey_capture = hotkey_capture
        self._audio_capture = audio_capture
        self._transcription_client = transcription_client
        self._text_injector = text_injector
        self._on_recording_started = on_recording_started
        self._on_recording_stopped = on_recording_stopped
        self._on_transcription_started = on_transcription_started
        self._on_transcription_completed = on_transcription_completed
        self._on_injection_completed = on_injection_completed

    def _record_audio_segment(self) -> AudioChunk:
        """Capture one audio segment using hold-to-record when available.

        Parameters:
            None.

        Returns:
            AudioChunk: Captured audio payload and metadata.

        Raises:
            RuntimeError: If underlying audio capture backend fails.

        Example:
            ``audio_chunk = service._record_audio_segment()``
        """

        start_monotonic = time.monotonic()
        if self._on_recording_started is not None:
            self._on_recording_started()

        try:
            record_while_pressed = getattr(self._audio_capture, "record_while_pressed", None)
            is_pressed = getattr(self._hotkey_capture, "is_pressed", None)

            if callable(record_while_pressed) and callable(is_pressed):
                audio_chunk = record_while_pressed(
                    is_pressed=is_pressed,
                    max_seconds=self._config.max_record_seconds,
                )
            else:
                # Fallback keeps compatibility with older test doubles and backends.
                audio_chunk = self._audio_capture.record(
                    max_seconds=self._config.max_record_seconds
                )
        finally:
            if self._on_recording_stopped is not None:
                elapsed = max(0.0, time.monotonic() - start_monotonic)
                self._on_recording_stopped(elapsed)

        return audio_chunk

    def run_once(self, timeout_seconds: float | None = None) -> ServiceRunResult:
        """Run a single iteration of the dictation pipeline.

        Parameters:
            timeout_seconds: Optional timeout for waiting on the hotkey trigger.

        Returns:
            ServiceRunResult: Outcome of a single pipeline cycle.

        Raises:
            ValueError: If timeout is provided as a negative value.

        Example:
            ``result = service.run_once(timeout_seconds=0.1)``
        """

        if timeout_seconds is not None and timeout_seconds < 0:
            raise ValueError("timeout_seconds cannot be negative.")

        triggered = self._hotkey_capture.wait_for_trigger(timeout_seconds=timeout_seconds)
        if not triggered:
            return ServiceRunResult(triggered=False, transcription=None, injected=False)

        audio_chunk = self._record_audio_segment()

        if self._on_transcription_started is not None:
            self._on_transcription_started()

        transcription = self._transcription_client.transcribe(audio_chunk).strip()
        if self._on_transcription_completed is not None:
            self._on_transcription_completed(transcription)

        # Whitespace-only transcriptions often indicate uncertain recognition;
        # skipping injection prevents unexpected text spam in the focused app.
        if not transcription:
            return ServiceRunResult(triggered=True, transcription="", injected=False)

        injection_result = self._text_injector.inject(transcription)
        if self._on_injection_completed is not None:
            self._on_injection_completed(injection_result)

        return ServiceRunResult(
            triggered=True,
            transcription=transcription,
            injected=injection_result.inserted,
            injection_result=injection_result,
        )

    def run_forever(self, max_iterations: int | None = None) -> None:
        """Run polling loop until interrupted or iteration limit is reached.

        Parameters:
            max_iterations: Optional cap used for tests or local dry runs.

        Returns:
            None.

        Raises:
            ValueError: If max_iterations is provided as a non-positive number.

        Example:
            ``service.run_forever(max_iterations=100)``
        """

        if max_iterations is not None and max_iterations <= 0:
            raise ValueError("max_iterations must be greater than 0 when provided.")

        iteration = 0
        while True:
            self.run_once(timeout_seconds=self._config.daemon_poll_interval_seconds)
            iteration += 1
            if max_iterations is not None and iteration >= max_iterations:
                return
