# flow-dictate

## What this repo is
`flow-dictate` is a macOS-first Python project for a lightweight "speak to type anywhere" workflow.
It combines global hotkey capture, microphone recording, transcription, and text insertion in one CLI.
The codebase now includes both deterministic stub backends for local development and a realtime OpenAI path for end-to-end dictation.

## Key features / scope
- macOS-only target for MVP (global hotkeys, permissions, and active-app insertion are macOS-specific).
- Python + `uv` for environment and dependency management.
- CLI-first workflow with two commands: `run` and `doctor`.
- Runtime backends:
  - `stub`: deterministic local runs and tests.
  - `realtime`: microphone capture + OpenAI Realtime transcription.
- Output modes:
  - `stdout`
  - `clipboard`
  - `active-app` (Command+V automation with clipboard fallback support)
- Permission preflight checks for Microphone, Accessibility, and Input Monitoring.

Out of scope for MVP:
- Cross-platform support.
- Multi-user cloud profiles.
- Full desktop settings GUI.

## Setup
1. Install `uv` (macOS):
```bash
brew install uv
```

2. Create a virtual environment:
```bash
uv venv
```

3. Sync dependencies (runtime + dev group):
```bash
uv sync --group dev
```

## How to run
Show CLI help:
```bash
uv run flow-dictate --help
```

Run permission preflight:
```bash
uv run flow-dictate doctor
uv run flow-dictate doctor --prompt-permissions
```

Run one dry cycle with stub backend:
```bash
uv run flow-dictate run --backend stub --run-once --simulate-trigger --use-stub-hotkey
```

Run one realtime cycle (microphone + OpenAI Realtime):
```bash
export OPENAI_API_KEY="your_key_here"
uv run flow-dictate run --backend realtime --run-once --simulate-trigger --use-stub-hotkey
```

Choose output mode:
```bash
uv run flow-dictate run --backend stub --run-once --simulate-trigger --output stdout
uv run flow-dictate run --backend stub --run-once --simulate-trigger --output clipboard
uv run flow-dictate run --backend stub --run-once --simulate-trigger --output active-app
```

Run tests:
```bash
uv run --group dev pytest
```

Run lint checks:
```bash
uv run --group dev ruff check .
```

Build the package:
```bash
uv build
```

## Configuration
Environment variables:
- `OPENAI_API_KEY`: API key used by realtime backend (or whichever variable name you configure below).
- `FLOW_DICTATE_BACKEND`: default backend (`stub` or `realtime`), default `stub`.
- `FLOW_DICTATE_HOTKEY`: hotkey string, default `cmd+shift+space`.
- `FLOW_DICTATE_SAMPLE_RATE_HZ`: integer sample rate, default `24000`.
- `FLOW_DICTATE_CHANNELS`: integer channel count, default `1`.
- `FLOW_DICTATE_AUDIO_INPUT_DEVICE`: optional microphone device id/name.
- `FLOW_DICTATE_MAX_RECORD_SECONDS`: float max recording window, default `30.0`.
- `FLOW_DICTATE_TRANSCRIPTION_MODEL`: transcription model id, default `gpt-4o-mini-transcribe`.
- `FLOW_DICTATE_OPENAI_API_KEY_ENV`: env var name for API key lookup, default `OPENAI_API_KEY`.
- `FLOW_DICTATE_REALTIME_WEBSOCKET_URL`: realtime websocket URL, default `wss://api.openai.com/v1/realtime`.
- `FLOW_DICTATE_REALTIME_CONNECT_TIMEOUT_SECONDS`: websocket connect timeout, default `15.0`.
- `FLOW_DICTATE_REALTIME_RESPONSE_TIMEOUT_SECONDS`: max wait for completed transcription event, default `30.0`.
- `FLOW_DICTATE_OUTPUT_MODE`: output destination (`stdout`, `clipboard`, `active-app`), default `stdout`.
- `FLOW_DICTATE_ACTIVE_APP_FALLBACK_TO_CLIPBOARD`: keep clipboard text when active-app paste fails, default `true`.
- `FLOW_DICTATE_TEMP_AUDIO_DIR`: temp path, default `/tmp/flow-dictate`.
- `FLOW_DICTATE_DAEMON_POLL_INTERVAL_SECONDS`: service loop poll delay, default `0.10`.

## Project structure
```text
.
├── docs/
│   ├── architecture.md
│   ├── implementation-plan.md
│   ├── research-notes.md
│   └── testing-guide.md
├── src/flow_dictate/
│   ├── __main__.py
│   ├── audio.py
│   ├── cli.py
│   ├── config.py
│   ├── hotkey.py
│   ├── injector.py
│   ├── interfaces.py
│   ├── permissions.py
│   ├── service.py
│   └── transcription.py
├── tests/
│   ├── test_audio.py
│   ├── test_config.py
│   ├── test_hotkey.py
│   ├── test_injector.py
│   ├── test_permissions.py
│   ├── test_service.py
│   └── test_transcription.py
├── pyproject.toml
└── uv.lock
```

## Contributing / development notes
- Keep functions small and explicit.
- Add docstrings for every new/changed function, method, and class.
- Add inline comments for non-obvious logic and tradeoffs.
- Add or update tests for behavior changes.
- Keep docs in sync with code changes:
  - `README.md`
  - `docs/implementation-plan.md`
  - `docs/testing-guide.md`
