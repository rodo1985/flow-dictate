"""Transcription clients for stub and OpenAI Realtime backends."""

from __future__ import annotations

import base64
import json
import os
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import numpy as np

from flow_dictate.config import AppConfig
from flow_dictate.interfaces import AudioChunk, TranscriptionClient


def _import_websocket() -> Any:
    """Import ``websocket-client`` lazily for realtime connections.

    Parameters:
        None.

    Returns:
        Any: Imported ``websocket`` module from ``websocket-client``.

    Raises:
        RuntimeError: If ``websocket-client`` is not available.

    Example:
        ``websocket = _import_websocket()``
    """

    try:
        import websocket  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI realtime transcription requires the 'websocket-client' package. "
            "Install dependencies with `uv sync`."
        ) from exc

    return websocket


def _build_realtime_websocket_url(base_url: str, model: str) -> str:
    """Build a realtime websocket URL with the transcription model query parameter.

    Parameters:
        base_url: Base websocket URL.
        model: Realtime model name.

    Returns:
        str: URL with ``model`` query param merged in.

    Raises:
        ValueError: If ``base_url`` or ``model`` is empty.

    Example:
        >>> _build_realtime_websocket_url("wss://api.openai.com/v1/realtime", "gpt-4o-mini-transcribe")
        'wss://api.openai.com/v1/realtime?model=gpt-4o-mini-transcribe'
    """

    if not base_url:
        raise ValueError("base_url must not be empty.")
    if not model:
        raise ValueError("model must not be empty.")

    parsed = urlparse(base_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["model"] = model

    updated = parsed._replace(query=urlencode(query))
    return urlunparse(updated)


def _prepare_audio_for_realtime(audio: AudioChunk) -> tuple[str, int]:
    """Convert an ``AudioChunk`` into base64 PCM payload accepted by Realtime.

    Parameters:
        audio: Captured audio payload and metadata.

    Returns:
        tuple[str, int]: Base64-encoded PCM16 payload and final sample rate.

    Raises:
        ValueError: If audio shape assumptions are violated.

    Example:
        ``payload, rate = _prepare_audio_for_realtime(audio_chunk)``
    """

    if len(audio.data) % 2 != 0:
        raise ValueError("Audio payload must contain an even number of bytes for PCM16.")

    sample_rate_hz = audio.sample_rate_hz
    pcm_samples = np.frombuffer(audio.data, dtype="<i2")

    if audio.channels < 1:
        raise ValueError("Audio chunk must have at least one channel.")
    if pcm_samples.size % audio.channels != 0:
        raise ValueError("Audio payload length is not divisible by the channel count.")

    if audio.channels == 1:
        mono_samples = pcm_samples.astype(np.float32)
    else:
        # We average channels to create a stable mono stream for the transcription API.
        # This avoids channel-selection bias with stereo or multi-channel inputs.
        frames = pcm_samples.reshape(-1, audio.channels).astype(np.float32)
        mono_samples = frames.mean(axis=1)

    if sample_rate_hz != 24_000:
        # Realtime PCM ingestion expects 24 kHz. Linear interpolation keeps
        # dependencies light while remaining adequate for transcription input.
        source_count = mono_samples.shape[0]
        target_count = max(1, int(round(source_count * 24_000 / sample_rate_hz)))
        if source_count == 1:
            resampled = np.full((target_count,), mono_samples[0], dtype=np.float32)
        else:
            source_positions = np.linspace(0.0, 1.0, num=source_count, dtype=np.float32)
            target_positions = np.linspace(0.0, 1.0, num=target_count, dtype=np.float32)
            resampled = np.interp(target_positions, source_positions, mono_samples).astype(
                np.float32
            )
        mono_samples = resampled
        sample_rate_hz = 24_000

    pcm16_mono = np.clip(mono_samples, -32768, 32767).astype("<i2")
    encoded = base64.b64encode(pcm16_mono.tobytes()).decode("ascii")
    return encoded, sample_rate_hz


def _is_websocket_timeout_error(exc: Exception) -> bool:
    """Return whether an exception represents a websocket receive timeout.

    Parameters:
        exc: Exception raised during websocket operations.

    Returns:
        bool: ``True`` when exception indicates a timeout.

    Raises:
        None.

    Example:
        ``timed_out = _is_websocket_timeout_error(exc)``
    """

    return exc.__class__.__name__ in {"WebSocketTimeoutException", "TimeoutError"}


def _create_websocket_connection(
    base_url: str,
    model: str,
    api_key: str,
    timeout_seconds: float,
) -> Any:
    """Create an authenticated websocket connection to OpenAI Realtime API.

    Parameters:
        base_url: Base websocket URL.
        model: Realtime transcription model.
        api_key: OpenAI API key.
        timeout_seconds: Socket connect timeout in seconds.

    Returns:
        Any: Connected websocket object from ``websocket-client``.

    Raises:
        RuntimeError: If websocket creation fails.

    Example:
        ``ws = _create_websocket_connection(base_url, model, api_key, timeout_seconds=15.0)``
    """

    websocket = _import_websocket()
    url = _build_realtime_websocket_url(base_url=base_url, model=model)
    headers = [
        f"Authorization: Bearer {api_key}",
        "OpenAI-Beta: realtime=v1",
    ]

    try:
        return websocket.create_connection(
            url=url,
            header=headers,
            timeout=timeout_seconds,
        )
    except Exception as exc:
        raise RuntimeError("Failed to connect to the OpenAI Realtime websocket endpoint.") from exc


def _extract_error_message(server_event: dict[str, Any]) -> str:
    """Extract a human-readable message from a server-side realtime error event.

    Parameters:
        server_event: Parsed JSON server event.

    Returns:
        str: Most specific error message available.

    Raises:
        None.

    Example:
        ``message = _extract_error_message(event)``
    """

    if isinstance(server_event.get("error"), dict):
        message = server_event["error"].get("message")
        if isinstance(message, str) and message:
            return message

    message = server_event.get("message")
    if isinstance(message, str) and message:
        return message

    return "OpenAI realtime transcription returned an unspecified error."


def _extract_completed_transcript(server_event: dict[str, Any]) -> str:
    """Extract transcript text from completed realtime events.

    Parameters:
        server_event: Parsed JSON server event from the websocket stream.

    Returns:
        str: Extracted transcript text, or an empty string when unavailable.

    Raises:
        None.

    Example:
        ``text = _extract_completed_transcript(event)``
    """

    transcript = server_event.get("transcript")
    if isinstance(transcript, str):
        return transcript.strip()

    response = server_event.get("response")
    if not isinstance(response, dict):
        return ""

    output = response.get("output")
    if not isinstance(output, list):
        return ""

    text_fragments: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            for key in ("transcript", "text"):
                value = block.get(key)
                if isinstance(value, str) and value:
                    text_fragments.append(value)

    return "".join(text_fragments).strip()


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
        >>> client.transcribe(AudioChunk(data=b"x", sample_rate_hz=24_000, channels=1))
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


class OpenAIRealtimeTranscriptionClient(TranscriptionClient):
    """Transcribe microphone audio via OpenAI Realtime transcription sessions.

    Parameters:
        api_key: OpenAI API key for websocket authentication.
        model: Realtime transcription model name.
        websocket_url: Realtime websocket base URL.
        connect_timeout_seconds: Timeout for websocket connection creation.
        response_timeout_seconds: Timeout while waiting for transcript events.

    Returns:
        OpenAIRealtimeTranscriptionClient: Realtime transcription backend.

    Raises:
        ValueError: If required values are invalid.

    Example:
        ``client = OpenAIRealtimeTranscriptionClient(api_key="sk-...", model="gpt-4o-mini-transcribe")``
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini-transcribe",
        websocket_url: str = "wss://api.openai.com/v1/realtime",
        connect_timeout_seconds: float = 15.0,
        response_timeout_seconds: float = 30.0,
    ) -> None:
        """Initialize realtime transcription client settings.

        Parameters:
            api_key: OpenAI API key.
            model: Realtime transcription model.
            websocket_url: Base websocket URL.
            connect_timeout_seconds: Connect timeout in seconds.
            response_timeout_seconds: Receive timeout in seconds.

        Returns:
            None.

        Raises:
            ValueError: If required values are empty or timeouts are non-positive.

        Example:
            ``OpenAIRealtimeTranscriptionClient(api_key="sk-...", model="gpt-4o-transcribe")``
        """

        if not api_key:
            raise ValueError("api_key must not be empty.")
        if not model:
            raise ValueError("model must not be empty.")
        if not websocket_url:
            raise ValueError("websocket_url must not be empty.")
        if connect_timeout_seconds <= 0:
            raise ValueError("connect_timeout_seconds must be greater than 0.")
        if response_timeout_seconds <= 0:
            raise ValueError("response_timeout_seconds must be greater than 0.")

        self._api_key = api_key
        self._model = model
        self._websocket_url = websocket_url
        self._connect_timeout_seconds = connect_timeout_seconds
        self._response_timeout_seconds = response_timeout_seconds

    @classmethod
    def from_config(
        cls,
        config: AppConfig,
        environ: Mapping[str, str] | None = None,
    ) -> "OpenAIRealtimeTranscriptionClient":
        """Build a realtime transcription client using ``AppConfig`` and environment.

        Parameters:
            config: Runtime application configuration.
            environ: Optional environment mapping for API key lookup.

        Returns:
            OpenAIRealtimeTranscriptionClient: Configured realtime transcription client.

        Raises:
            ValueError: If the configured API key environment variable is not set.

        Example:
            ``client = OpenAIRealtimeTranscriptionClient.from_config(config)``
        """

        env = environ if environ is not None else os.environ
        api_key = env.get(config.openai_api_key_env, "").strip()
        if not api_key:
            raise ValueError(
                f"Environment variable '{config.openai_api_key_env}' is required for realtime transcription."
            )

        return cls(
            api_key=api_key,
            model=config.transcription_model,
            websocket_url=config.realtime_websocket_url,
            connect_timeout_seconds=config.realtime_connect_timeout_seconds,
            response_timeout_seconds=config.realtime_response_timeout_seconds,
        )

    def transcribe(self, audio: AudioChunk) -> str:
        """Transcribe an ``AudioChunk`` using the OpenAI Realtime API.

        Parameters:
            audio: PCM16 audio chunk captured from microphone input.

        Returns:
            str: Final transcript text from the completed transcription event.

        Raises:
            RuntimeError: If connection, server, or timeout failures occur.

        Example:
            ``transcript = client.transcribe(audio_chunk)``
        """

        if not audio.data:
            return ""

        encoded_audio, sample_rate_hz = _prepare_audio_for_realtime(audio)
        websocket = _create_websocket_connection(
            base_url=self._websocket_url,
            model=self._model,
            api_key=self._api_key,
            timeout_seconds=self._connect_timeout_seconds,
        )

        try:
            websocket.settimeout(self._response_timeout_seconds)
            websocket.send(
                json.dumps(
                    {
                        "type": "session.update",
                        "session": {
                            "type": "transcription",
                            "audio": {
                                "input": {
                                    "format": {"type": "audio/pcm", "rate": sample_rate_hz},
                                    "transcription": {"model": self._model},
                                    "turn_detection": None,
                                }
                            },
                        },
                    }
                )
            )
            websocket.send(
                json.dumps(
                    {
                        "type": "input_audio_buffer.append",
                        "audio": encoded_audio,
                    }
                )
            )
            websocket.send(json.dumps({"type": "input_audio_buffer.commit"}))
            websocket.send(json.dumps({"type": "response.create"}))

            partial_fragments: list[str] = []
            while True:
                try:
                    raw_message = websocket.recv()
                except Exception as exc:
                    if _is_websocket_timeout_error(exc):
                        partial = "".join(partial_fragments).strip()
                        if partial:
                            return partial
                        raise RuntimeError(
                            "Timed out waiting for a completed realtime transcription event."
                        ) from exc
                    raise RuntimeError("Failed while waiting for realtime transcription events.") from exc

                server_event = json.loads(raw_message)
                event_type = server_event.get("type")

                if event_type in {
                    "conversation.item.input_audio_transcription.delta",
                    "response.audio_transcript.delta",
                }:
                    partial_fragments.append(str(server_event.get("delta", "")))
                    continue

                if event_type in {
                    "conversation.item.input_audio_transcription.completed",
                    "response.audio_transcript.done",
                    "response.completed",
                }:
                    completed_transcript = _extract_completed_transcript(server_event)
                    if completed_transcript:
                        return completed_transcript
                    return "".join(partial_fragments).strip()

                if event_type == "error":
                    raise RuntimeError(_extract_error_message(server_event))
        finally:
            websocket.close()
