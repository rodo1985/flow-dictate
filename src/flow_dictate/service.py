"""Service orchestration for flow-dictate."""

from __future__ import annotations

from dataclasses import dataclass

from flow_dictate.config import AppConfig
from flow_dictate.interfaces import AudioCapture, HotkeyCapture, TextInjector, TranscriptionClient


@dataclass(frozen=True, slots=True)
class ServiceRunResult:
    """Summarize one iteration of the dictation service loop.

    Parameters:
        triggered: Whether a hotkey trigger was observed.
        transcription: Text produced by transcription, if any.
        injected: Whether text was sent to the injector.

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
    ) -> None:
        """Store orchestration dependencies.

        Parameters:
            config: Runtime configuration object.
            hotkey_capture: Trigger listener implementation.
            audio_capture: Audio capture implementation.
            transcription_client: Audio-to-text implementation.
            text_injector: Text injection implementation.

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

        audio_chunk = self._audio_capture.record(max_seconds=self._config.max_record_seconds)
        transcription = self._transcription_client.transcribe(audio_chunk).strip()

        # Whitespace-only transcriptions often indicate uncertain recognition;
        # skipping injection prevents unexpected text spam in the focused app.
        if not transcription:
            return ServiceRunResult(triggered=True, transcription="", injected=False)

        self._text_injector.inject(transcription)
        return ServiceRunResult(
            triggered=True,
            transcription=transcription,
            injected=True,
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
