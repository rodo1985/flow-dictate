"""Tests for OpenAI realtime transcription integration logic."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

import pytest

import flow_dictate.transcription as transcription_module
from flow_dictate.config import AppConfig
from flow_dictate.interfaces import AudioChunk
from flow_dictate.transcription import (
    OpenAIRealtimeTranscriptionClient,
    _prepare_audio_for_realtime,
)


@dataclass
class _FakeWebSocket:
    """Simple fake websocket that replays canned server events.

    Parameters:
        server_events: Ordered server events returned from ``recv``.

    Returns:
        _FakeWebSocket: Fake websocket connection object.

    Raises:
        None.

    Example:
        ``fake_ws = _FakeWebSocket(server_events=[{"type": "session.created"}])``
    """

    server_events: list[dict[str, Any]]

    def __post_init__(self) -> None:
        """Initialize state for send history and timeout tracking.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``fake_ws.__post_init__()``
        """

        self.sent_events: list[dict[str, Any]] = []
        self.timeout_seconds: float | None = None
        self.closed = False

    def settimeout(self, timeout_seconds: float) -> None:
        """Store timeout for assertion.

        Parameters:
            timeout_seconds: Timeout configured by client.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``fake_ws.settimeout(30.0)``
        """

        self.timeout_seconds = timeout_seconds

    def send(self, payload: str) -> None:
        """Capture outbound JSON event payloads.

        Parameters:
            payload: JSON-serialized realtime client event.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``fake_ws.send("{\"type\": \"session.update\"}")``
        """

        self.sent_events.append(json.loads(payload))

    def recv(self) -> str:
        """Return next server event or raise timeout when exhausted.

        Parameters:
            None.

        Returns:
            str: JSON-serialized server event.

        Raises:
            TimeoutError: When no more events are available.

        Example:
            ``raw = fake_ws.recv()``
        """

        if not self.server_events:
            raise TimeoutError("timed out")
        return json.dumps(self.server_events.pop(0))

    def close(self) -> None:
        """Mark websocket as closed.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            None.

        Example:
            ``fake_ws.close()``
        """

        self.closed = True


def test_from_config_requires_api_key_env_var() -> None:
    """Verify config-based client creation fails when API key is missing.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If expected ``ValueError`` is not raised.

    Example:
        ``pytest -k test_from_config_requires_api_key_env_var``
    """

    config = AppConfig(openai_api_key_env="MISSING_API_KEY")

    with pytest.raises(ValueError, match="MISSING_API_KEY"):
        OpenAIRealtimeTranscriptionClient.from_config(config=config, environ={})


def test_transcribe_sends_expected_realtime_events(monkeypatch: Any) -> None:
    """Verify realtime client sends session/update audio events and returns transcript.

    Parameters:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        AssertionError: If event flow or parsed transcript regresses.

    Example:
        ``pytest -k test_transcribe_sends_expected_realtime_events``
    """

    fake_ws = _FakeWebSocket(
        server_events=[
            {"type": "session.created"},
            {"type": "conversation.item.input_audio_transcription.delta", "delta": "hello "},
            {
                "type": "conversation.item.input_audio_transcription.completed",
                "transcript": "hello world",
            },
        ]
    )

    monkeypatch.setattr(
        transcription_module,
        "_create_websocket_connection",
        lambda **_: fake_ws,
    )

    client = OpenAIRealtimeTranscriptionClient(
        api_key="test-key",
        model="gpt-4o-mini-transcribe",
        websocket_url="wss://api.openai.com/v1/realtime",
    )
    transcript = client.transcribe(
        AudioChunk(
            data=(b"\x00\x01" * 128),
            sample_rate_hz=24_000,
            channels=1,
        )
    )

    assert transcript == "hello world"
    assert fake_ws.timeout_seconds == 30.0
    assert fake_ws.closed is True

    assert fake_ws.sent_events[0]["type"] == "session.update"
    assert fake_ws.sent_events[0]["session"]["type"] == "transcription"
    assert fake_ws.sent_events[1]["type"] == "input_audio_buffer.append"
    assert isinstance(fake_ws.sent_events[1]["audio"], str)
    assert fake_ws.sent_events[2] == {"type": "input_audio_buffer.commit"}


def test_transcribe_returns_partial_text_on_timeout(monkeypatch: Any) -> None:
    """Verify partial transcript is returned when completion event times out.

    Parameters:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        AssertionError: If timeout fallback behavior regresses.

    Example:
        ``pytest -k test_transcribe_returns_partial_text_on_timeout``
    """

    fake_ws = _FakeWebSocket(
        server_events=[
            {"type": "conversation.item.input_audio_transcription.delta", "delta": "hello "},
            {"type": "conversation.item.input_audio_transcription.delta", "delta": "there"},
        ]
    )
    monkeypatch.setattr(
        transcription_module,
        "_create_websocket_connection",
        lambda **_: fake_ws,
    )

    client = OpenAIRealtimeTranscriptionClient(api_key="test-key")
    transcript = client.transcribe(
        AudioChunk(data=(b"\x00\x01" * 128), sample_rate_hz=24_000, channels=1)
    )

    assert transcript == "hello there"


def test_prepare_audio_for_realtime_resamples_to_24khz() -> None:
    """Verify helper resamples PCM16 payloads to the required 24 kHz format.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If resampling output is malformed.

    Example:
        ``pytest -k test_prepare_audio_for_realtime_resamples_to_24khz``
    """

    original = AudioChunk(
        data=(b"\x00\x00" * 240),
        sample_rate_hz=12_000,
        channels=1,
    )

    encoded_audio, sample_rate_hz = _prepare_audio_for_realtime(original)
    decoded_audio = base64.b64decode(encoded_audio)

    assert sample_rate_hz == 24_000
    assert len(decoded_audio) > len(original.data)
