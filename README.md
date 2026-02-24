# flow-dictate

## What this repo is
`flow-dictate` is a macOS-first Python project to build a lightweight "speak to type anywhere" tool.
The goal is a personal, terminal-installed dictation daemon inspired by Wispr Flow / WhisperFlow behavior:
hold a hotkey, speak, transcribe with OpenAI models, and inject text into your active app.
This repository is currently in scaffold + architecture phase, with interfaces and tests ready for implementation.

## Key features and scope
- macOS-only target (no Windows/Linux support planned for MVP).
- Python + `uv` workflow for dependency and command management.
- CLI-first architecture (no full desktop GUI planned for MVP).
- Modular design for hotkey capture, audio capture, transcription, and text injection.
- Current scaffold includes stub implementations and orchestration tests.

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
uv run flow-dictate doctor
uv run flow-dictate run --run-once --simulate-trigger
uv run python -m flow_dictate run --run-once --simulate-trigger
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
Environment variables (current scaffold):
- `OPENAI_API_KEY`: your OpenAI API key (required once real API client is enabled).
- `FLOW_DICTATE_HOTKEY`: hotkey string, default `cmd+shift+space`.
- `FLOW_DICTATE_SAMPLE_RATE_HZ`: integer sample rate, default `16000`.
- `FLOW_DICTATE_CHANNELS`: integer channels count, default `1`.
- `FLOW_DICTATE_MAX_RECORD_SECONDS`: float max recording window, default `30.0`.
- `FLOW_DICTATE_TRANSCRIPTION_MODEL`: model id, default `gpt-4o-mini-transcribe`.
- `FLOW_DICTATE_OPENAI_API_KEY_ENV`: env var name for API key lookup, default `OPENAI_API_KEY`.
- `FLOW_DICTATE_TEMP_AUDIO_DIR`: temp path, default `/tmp/flow-dictate`.
- `FLOW_DICTATE_DAEMON_POLL_INTERVAL_SECONDS`: loop poll delay, default `0.10`.

Permission preflight:
- `uv run flow-dictate doctor` checks Microphone, Accessibility, and Input Monitoring.
- `uv run flow-dictate doctor --prompt-permissions` may trigger macOS permission prompts where supported.

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
│   ├── injector.py
│   └── permissions.py
├── tests/
│   ├── test_config.py
│   ├── test_hotkey.py
│   ├── test_permissions.py
│   └── test_service.py
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
