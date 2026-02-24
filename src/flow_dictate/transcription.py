"""Transcription client stubs and placeholders."""

from __future__ import annotations

from flow_dictate.interfaces import AudioChunk, TranscriptionClient


class StubOpenAITranscriptionClient(TranscriptionClient):
    """Provide deterministic transcription without external network calls.

    Parameters:
        default_text: Text returned when audio payload is non-empty.

    Returns:
        StubOpenAITranscriptionClient: Offline transcription stub.

    Raises:
        None.

    Example:
        >>> client = StubOpenAITranscriptionClient(default_text="hello")
        >>> client.transcribe(AudioChunk(data=b"x", sample_rate_hz=16_000, channels=1))
        'hello'
    """

    def __init__(self, default_text: str = "stub transcript") -> None:
        """Initialize the stub transcription response.

        Parameters:
            default_text: Text to return for non-empty audio chunks.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``StubOpenAITranscriptionClient(default_text="hello world")``
        """

        self._default_text = default_text

    def transcribe(self, audio: AudioChunk) -> str:
        """Return deterministic text derived from audio presence.

        Parameters:
            audio: Audio payload to transcribe.

        Returns:
            str: ``default_text`` for non-empty data, otherwise an empty string.

        Raises:
            None.

        Example:
            ``client.transcribe(audio_chunk)``
        """

        if not audio.data:
            return ""

        return self._default_text
