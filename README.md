# flow-dictate

## What this repo is
`flow-dictate` is a macOS-first Python project to build a lightweight "speak to type anywhere" tool.
The goal is a personal, terminal-installed dictation daemon inspired by Wispr Flow / WhisperFlow behavior:
hold a hotkey, speak, transcribe with OpenAI models, and inject text into your active app.
This repository now includes an initial end-to-end backend implementation with real microphone capture, realtime transcription, and testable fallbacks.

## Key features and scope
- macOS-only target (no Windows/Linux support planned for MVP).
- Python + `uv` workflow for dependency and command management.
- CLI-first architecture (no full desktop GUI planned for MVP).
- Modular design for hotkey capture, audio capture, transcription, and text injection.
- Includes a working realtime backend: microphone capture + OpenAI Realtime transcription.
- Includes a stub backend for offline development and deterministic tests.

Out of scope for MVP right now:
- Cross-platform support.
- Multi-user cloud profiles.
- Full settings GUI.

## Setup
1. Install `uv` (if not already installed):
```bash
brew install uv
```

2. Create and activate the project environment:
```bash
uv venv
```

3. Sync dependencies:
```bash
uv sync --group dev
```

## How to run
Development and exploration:
```bash
uv run flow-dictate --help
uv run flow-dictate --backend stub --run-once --simulate-trigger
uv run python -m flow_dictate --backend stub --run-once --simulate-trigger
```

Realtime dictation (records from microphone and transcribes with OpenAI):
```bash
export OPENAI_API_KEY="your_key_here"
uv run flow-dictate --backend realtime --run-once --simulate-trigger
```

Tests:
```bash
uv run --group dev pytest
```

Lint:
```bash
uv run --group dev ruff check .
```

Build package:
```bash
uv build
```

## Configuration
Environment variables:
- `OPENAI_API_KEY`: your OpenAI API key (required for realtime backend).
- `FLOW_DICTATE_HOTKEY`: hotkey string, default `cmd+shift+space`.
- `FLOW_DICTATE_SAMPLE_RATE_HZ`: integer sample rate, default `24000`.
- `FLOW_DICTATE_CHANNELS`: integer channels count, default `1`.
- `FLOW_DICTATE_AUDIO_INPUT_DEVICE`: optional microphone device id/name.
- `FLOW_DICTATE_MAX_RECORD_SECONDS`: float max recording window, default `30.0`.
- `FLOW_DICTATE_TRANSCRIPTION_MODEL`: model id, default `gpt-4o-mini-transcribe`.
- `FLOW_DICTATE_OPENAI_API_KEY_ENV`: env var name for API key lookup, default `OPENAI_API_KEY`.
- `FLOW_DICTATE_REALTIME_WEBSOCKET_URL`: websocket URL, default `wss://api.openai.com/v1/realtime`.
- `FLOW_DICTATE_REALTIME_CONNECT_TIMEOUT_SECONDS`: websocket connect timeout, default `15.0`.
- `FLOW_DICTATE_REALTIME_RESPONSE_TIMEOUT_SECONDS`: max wait for completed transcription event, default `30.0`.
- `FLOW_DICTATE_TEMP_AUDIO_DIR`: temp path, default `/tmp/flow-dictate`.
- `FLOW_DICTATE_DAEMON_POLL_INTERVAL_SECONDS`: loop poll delay, default `0.10`.

## Project structure
```text
.
├── docs/
│   ├── architecture.md
│   ├── implementation-plan.md
│   └── research-notes.md
├── src/flow_dictate/
│   ├── cli.py
│   ├── config.py
│   ├── interfaces.py
│   ├── service.py
│   ├── hotkey.py
│   ├── audio.py
│   ├── transcription.py
│   └── injector.py
├── tests/
│   ├── test_audio.py
│   ├── test_config.py
│   ├── test_service.py
│   └── test_transcription.py
└── pyproject.toml
```

## Contributing and development notes
- Keep code straightforward and typed.
- Add docstrings for every new/changed function, method, and class.
- Add tests for behavior changes.
- Keep docs updated with each workflow/configuration change:
  - [docs/architecture.md](docs/architecture.md)
  - [docs/implementation-plan.md](docs/implementation-plan.md)
  - [docs/research-notes.md](docs/research-notes.md)
