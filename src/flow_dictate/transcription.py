"""Transcription clients for stub, OpenAI Audio API, and Realtime backends."""

from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
from typing import Any, Mapping
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
import uuid
import wave

import numpy as np

from flow_dictate.config import AppConfig
from flow_dictate.interfaces import AudioChunk, TranscriptionClient

DEFAULT_AUDIO_TRANSCRIPTION_URL = "https://api.openai.com/v1/audio/transcriptions"


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


def _load_dotenv_values(path: Path) -> dict[str, str]:
    """Load simple ``KEY=VALUE`` pairs from a dotenv file.

    Parameters:
        path: Path to dotenv file.

    Returns:
        dict[str, str]: Parsed environment key-value pairs.

    Raises:
        RuntimeError: If file reads fail.

    Example:
        ``values = _load_dotenv_values(Path(".env"))``
    """

    if not path.exists():
        return {}

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Unable to read dotenv file at {path}.") from exc

    parsed: dict[str, str] = {}
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].strip()

        if "=" not in stripped:
            continue

        key, raw_value = stripped.split("=", 1)
        normalized_key = key.strip()
        if not normalized_key:
            continue

        value = raw_value.strip()
        if (
            len(value) >= 2
            and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'"))
        ):
            value = value[1:-1]

        parsed[normalized_key] = value

    return parsed


def _resolve_runtime_environment(environ: Mapping[str, str] | None = None) -> Mapping[str, str]:
    """Resolve runtime environment values with `.env` support.

    Parameters:
        environ: Optional explicit environment mapping.

    Returns:
        Mapping[str, str]: Environment values used for API-key lookups.

    Raises:
        RuntimeError: If reading `.env` fails.

    Example:
        ``env = _resolve_runtime_environment()```
    """

    if environ is not None:
        return environ

    # Process environment wins over `.env` so shell overrides remain predictable.
    return {
        **_load_dotenv_values(Path.cwd() / ".env"),
        **os.environ,
    }


def _to_mono_pcm16_bytes(audio: AudioChunk) -> tuple[bytes, int]:
    """Normalize a chunk into mono PCM16 bytes and sample rate metadata.

    Parameters:
        audio: Captured audio payload and metadata.

    Returns:
        tuple[bytes, int]: Mono PCM16 bytes and sample rate.

    Raises:
        ValueError: If payload shape assumptions are violated.

    Example:
        ``pcm_bytes, sample_rate = _to_mono_pcm16_bytes(audio_chunk)``
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
        # We average channels to create a stable mono stream across hardware layouts.
        frames = pcm_samples.reshape(-1, audio.channels).astype(np.float32)
        mono_samples = frames.mean(axis=1)

    pcm16_mono = np.clip(mono_samples, -32768, 32767).astype("<i2")
    return pcm16_mono.tobytes(), sample_rate_hz


def _audio_chunk_to_wav_bytes(audio: AudioChunk) -> bytes:
    """Convert an ``AudioChunk`` into an in-memory WAV file payload.

    Parameters:
        audio: Captured audio payload and metadata.

    Returns:
        bytes: WAV file bytes suitable for Audio API upload.

    Raises:
        ValueError: If audio metadata or shape is invalid.

    Example:
        ``wav_bytes = _audio_chunk_to_wav_bytes(audio_chunk)``
    """

    pcm16_mono_bytes, sample_rate_hz = _to_mono_pcm16_bytes(audio)

    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate_hz)
        wav_file.writeframes(pcm16_mono_bytes)

    return wav_buffer.getvalue()


def _encode_multipart_form_data(
    fields: Mapping[str, str],
    file_field_name: str,
    filename: str,
    file_content_type: str,
    file_bytes: bytes,
) -> tuple[bytes, str]:
    """Encode fields and one file into a multipart/form-data payload.

    Parameters:
        fields: Form fields for model/config options.
        file_field_name: Name of the multipart file field.
        filename: Logical file name presented to the API.
        file_content_type: MIME type for uploaded file.
        file_bytes: File content bytes.

    Returns:
        tuple[bytes, str]: HTTP request body and ``Content-Type`` header value.

    Raises:
        ValueError: If required field names are empty.

    Example:
        ``body, content_type = _encode_multipart_form_data(...)``
    """

    if not file_field_name:
        raise ValueError("file_field_name must not be empty.")
    if not filename:
        raise ValueError("filename must not be empty.")

    boundary = f"----flowdictate-{uuid.uuid4().hex}"
    body_parts: list[bytes] = []

    for key, value in fields.items():
        body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
        body_parts.append(
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8")
        )
        body_parts.append(value.encode("utf-8"))
        body_parts.append(b"\r\n")

    body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
    body_parts.append(
        (
            f'Content-Disposition: form-data; name="{file_field_name}"; '
            f'filename="{filename}"\r\n'
        ).encode("utf-8")
    )
    body_parts.append(f"Content-Type: {file_content_type}\r\n\r\n".encode("utf-8"))
    body_parts.append(file_bytes)
    body_parts.append(b"\r\n")
    body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))

    body = b"".join(body_parts)
    content_type = f"multipart/form-data; boundary={boundary}"
    return body, content_type


def _extract_http_error_message(exc: urllib_error.HTTPError) -> str:
    """Extract a human-readable error from an HTTPError response body.

    Parameters:
        exc: HTTP error raised by ``urllib``.

    Returns:
        str: Most specific error message available.

    Raises:
        None.

    Example:
        ``message = _extract_http_error_message(exc)``
    """

    try:
        response_body = exc.read().decode("utf-8")
    except Exception:
        response_body = ""

    if response_body:
        try:
            parsed = json.loads(response_body)
        except json.JSONDecodeError:
            parsed = {}

        if isinstance(parsed, dict):
            if isinstance(parsed.get("error"), dict):
                message = parsed["error"].get("message")
                if isinstance(message, str) and message:
                    return message

            message = parsed.get("message")
            if isinstance(message, str) and message:
                return message

    return f"Audio transcription request failed with HTTP {exc.code}."


def _post_audio_transcription_request(
    transcription_url: str,
    api_key: str,
    model: str,
    wav_audio_bytes: bytes,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Submit a WAV file to OpenAI Audio API transcriptions endpoint.

    Parameters:
        transcription_url: URL for ``/v1/audio/transcriptions``.
        api_key: OpenAI API key.
        model: Transcription model id.
        wav_audio_bytes: WAV payload bytes.
        timeout_seconds: Request timeout in seconds.

    Returns:
        dict[str, Any]: Parsed JSON response payload.

    Raises:
        RuntimeError: If request fails or response payload is invalid.

    Example:
        ``payload = _post_audio_transcription_request(...)``
    """

    body, content_type = _encode_multipart_form_data(
        fields={
            "model": model,
            "response_format": "json",
        },
        file_field_name="file",
        filename="dictation.wav",
        file_content_type="audio/wav",
        file_bytes=wav_audio_bytes,
    )

    request = urllib_request.Request(
        url=transcription_url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": content_type,
        },
        method="POST",
    )

    try:
        with urllib_request.urlopen(request, timeout=timeout_seconds) as response:
            response_text = response.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        raise RuntimeError(_extract_http_error_message(exc)) from exc
    except TimeoutError as exc:
        raise RuntimeError("Timed out waiting for audio transcription response.") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError("Failed to connect to OpenAI audio transcription endpoint.") from exc

    try:
        parsed_payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Audio transcription response was not valid JSON.") from exc

    if not isinstance(parsed_payload, dict):
        raise RuntimeError("Audio transcription response payload had an unexpected shape.")

    return parsed_payload


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

    mono_pcm_bytes, sample_rate_hz = _to_mono_pcm16_bytes(audio)
    mono_samples = np.frombuffer(mono_pcm_bytes, dtype="<i2").astype(np.float32)

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


class OpenAIAudioTranscriptionClient(TranscriptionClient):
    """Transcribe audio by uploading WAV data to OpenAI Audio API.

    Parameters:
        api_key: OpenAI API key for HTTP authentication.
        model: Audio transcription model name.
        transcription_url: HTTP endpoint for transcription requests.
        request_timeout_seconds: Request timeout in seconds.

    Returns:
        OpenAIAudioTranscriptionClient: HTTP transcription backend.

    Raises:
        ValueError: If required values are invalid.

    Example:
        ``client = OpenAIAudioTranscriptionClient(api_key="sk-...", model="gpt-4o-mini-transcribe")``
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini-transcribe",
        transcription_url: str = DEFAULT_AUDIO_TRANSCRIPTION_URL,
        request_timeout_seconds: float = 30.0,
    ) -> None:
        """Initialize audio-transcription client settings.

        Parameters:
            api_key: OpenAI API key.
            model: Audio transcription model id.
            transcription_url: HTTP endpoint for transcription requests.
            request_timeout_seconds: Request timeout in seconds.

        Returns:
            None.

        Raises:
            ValueError: If required values are empty or timeout is non-positive.

        Example:
            ``OpenAIAudioTranscriptionClient(api_key="sk-...", model="gpt-4o-transcribe")``
        """

        if not api_key:
            raise ValueError("api_key must not be empty.")
        if not model:
            raise ValueError("model must not be empty.")
        if not transcription_url:
            raise ValueError("transcription_url must not be empty.")
        if request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be greater than 0.")

        self._api_key = api_key
        self._model = model
        self._transcription_url = transcription_url
        self._request_timeout_seconds = request_timeout_seconds

    @classmethod
    def from_config(
        cls,
        config: AppConfig,
        environ: Mapping[str, str] | None = None,
    ) -> "OpenAIAudioTranscriptionClient":
        """Build an HTTP transcription client using ``AppConfig`` and environment.

        Parameters:
            config: Runtime application configuration.
            environ: Optional environment mapping for API key lookup.

        Returns:
            OpenAIAudioTranscriptionClient: Configured HTTP transcription client.

        Raises:
            ValueError: If the configured API key environment variable is not set.

        Example:
            ``client = OpenAIAudioTranscriptionClient.from_config(config)``
        """

        env = _resolve_runtime_environment(environ=environ)
        api_key = env.get(config.openai_api_key_env, "").strip()
        if not api_key:
            raise ValueError(
                f"Environment variable '{config.openai_api_key_env}' is required for audio transcription."
            )

        return cls(
            api_key=api_key,
            model=config.transcription_model,
            request_timeout_seconds=config.realtime_response_timeout_seconds,
        )

    def transcribe(self, audio: AudioChunk) -> str:
        """Transcribe an ``AudioChunk`` using OpenAI ``/audio/transcriptions``.

        Parameters:
            audio: PCM16 audio chunk captured from microphone input.

        Returns:
            str: Final transcript text from the API response.

        Raises:
            RuntimeError: If upload/transcription fails or payload is malformed.

        Example:
            ``transcript = client.transcribe(audio_chunk)``
        """

        if not audio.data:
            return ""

        wav_audio_bytes = _audio_chunk_to_wav_bytes(audio)
        payload = _post_audio_transcription_request(
            transcription_url=self._transcription_url,
            api_key=self._api_key,
            model=self._model,
            wav_audio_bytes=wav_audio_bytes,
            timeout_seconds=self._request_timeout_seconds,
        )

        transcript = payload.get("text")
        if isinstance(transcript, str):
            return transcript.strip()

        raise RuntimeError("Audio transcription response did not include a text transcript.")


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

        env = _resolve_runtime_environment(environ=environ)
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
