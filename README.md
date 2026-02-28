# flow-dictate

## What this repo is
`flow-dictate` is a macOS-first Python project for a lightweight "speak to type anywhere" workflow.
It combines global hotkey capture, microphone recording, transcription, and text insertion in one CLI.
The codebase now includes deterministic local stubs, OpenAI Audio API transcription, an optional OpenAI Realtime backend, and a new Swift menu-bar shell for team-alpha desktop runs.

## Key features / scope
- macOS-only target for MVP (global hotkeys, permissions, and active-app insertion are macOS-specific).
- Python + `uv` for environment and dependency management.
- CLI workflow commands: `run`, `daemon`, `doctor`, and `hotkey-setup`.
- Runtime backends:
  - `stub`: deterministic local runs and tests.
  - `api`: microphone capture + OpenAI `/audio/transcriptions` upload (recommended).
  - `realtime`: optional websocket transcription mode.
- Hold-to-record behavior:
  - press and hold the configured hotkey to record
  - release the hotkey to stop recording and trigger transcription
  - terminal recording indicator shows start/stop recording status
- Output modes:
  - `stdout`
  - `clipboard`
  - `active-app` (supports `clipboard-paste` and `direct-type` insertion strategies)
- Permission preflight checks for Microphone, Accessibility, and Input Monitoring.
- App-shell integration:
  - daemon JSONL runtime events for menu-bar/HUD clients
  - machine-readable permission report via `doctor --json`

Out of scope for MVP:
- Cross-platform support.
- Multi-user cloud profiles.
- Full desktop settings GUI.
- Docker-based end-user desktop installation.

## macOS App Roadmap
- Canonical roadmap: [docs/macos-productization-roadmap.md](docs/macos-productization-roadmap.md)
- Phase 1 details: [docs/macos-phase-1-plan.md](docs/macos-phase-1-plan.md)
- Phase 2 details: [docs/macos-phase-2-plan.md](docs/macos-phase-2-plan.md)

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

Optional shortcut for steps 2-3:
```bash
make setup
```

4. Create your local environment file:
```bash
cp .env.example .env
```

5. (Optional) Capture your preferred hotkey directly from keyboard:
```bash
uv run flow-dictate hotkey-setup
```

## How to run
If you prefer `make` wrappers for common commands:
```bash
make help
make run BACKEND=api OUTPUT=active-app
make run-stub
make daemon BACKEND=api OUTPUT=active-app
make doctor-json
make check
make swift-build
make swift-test
```

Equivalent direct `uv` / Swift commands are listed below.

Show CLI help:
```bash
uv run flow-dictate --help
```

Run permission preflight:
```bash
uv run flow-dictate doctor
uv run flow-dictate doctor --prompt-permissions
uv run flow-dictate doctor --json
```

Run one dry cycle with stub backend:
```bash
uv run flow-dictate run --backend stub --run-once --simulate-trigger --use-stub-hotkey
```

Run API transcription mode (recommended):
```bash
uv run flow-dictate run --backend api
```

Run realtime mode (advanced):
```bash
uv run flow-dictate run --backend realtime
```

Run one realtime dry cycle without real hotkey capture (debug only):
```bash
uv run flow-dictate run --backend realtime --run-once --simulate-trigger --use-stub-hotkey
```

Choose output mode:
```bash
uv run flow-dictate run --backend api --output stdout
uv run flow-dictate run --backend api --output clipboard
uv run flow-dictate run --backend api --output active-app
```

Run daemon mode (JSONL events for app shells):
```bash
uv run flow-dictate daemon --output active-app
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

Build Swift menu-bar shell:
```bash
swift build --package-path macos/FlowDictateApp
```

## Team-alpha app install/run (macOS)
Prerequisites:
- `uv` installed (`brew install uv`)
- Xcode Command Line Tools installed (`xcode-select --install`)
- Swift toolchain available (`swift --version`)

Note:
- Installer captures the absolute `uv` path and injects it into the app launcher, so Finder launches can resolve `uv` reliably.
- Installer writes `NSMicrophoneUsageDescription` into the app bundle so microphone permission prompts can be shown safely.

Install:
```bash
./scripts/install_team_alpha_macos.sh
# or:
make app-install
```

Launch:
```bash
open /Applications/FlowDictate.app
# or:
make app-open
```

After launch:
- Look for the Flow Dictate icon in the macOS menu bar (top-right).
- Open the menu-bar icon to access `Open Setup`, `Open Settings`, worker controls, and `Launch at Login`.
- Setup reopens automatically if required permissions are missing.
- Use `Request Permissions` inside setup to jump to the next missing permission page. When Microphone is missing, the app also triggers a direct microphone request.
- Use direct setup buttons (`Open Microphone`, `Open Accessibility`, `Open Input Monitoring`) to jump to each exact privacy page.
- Use `Open Logs` from the menu-bar app to inspect runtime diagnostics.

## App Settings (macOS app mode)
The macOS app now uses app-managed settings for deterministic startup:
- API key source: Keychain (`service=ai.flowdictate.desktop`, `account=OPENAI_API_KEY`).
- Hotkey source: app settings (`Open Settings` in menu bar), validated and canonicalized before worker launch.
- Forced app runtime policy:
  - `FLOW_DICTATE_BACKEND=api`
  - `FLOW_DICTATE_OUTPUT_MODE=active-app`
  - `FLOW_DICTATE_ACTIVE_APP_INSERTION_STRATEGY=direct-type`

One-time migration on first app launch:
- If Keychain API key is empty and `.env` contains `OPENAI_API_KEY`, the key is imported into Keychain.
- If app hotkey is empty and `.env` contains a valid hotkey, it is imported.
- If `.env` hotkey is modifier-only or invalid, app hotkey defaults to `cmd+shift+space`.
- After migration, app settings do not sync back to `.env`.

Important:
- CLI behavior is unchanged and remains `.env`-driven.
- App mode and CLI mode can run with different hotkeys and API key sources by design.

Log file location:
```bash
~/Library/Logs/FlowDictate/flow-dictate-app.log
```

Live tail:
```bash
tail -f ~/Library/Logs/FlowDictate/flow-dictate-app.log
```

If logs show `env: uv: No such file or directory`, reinstall the app to refresh the launcher with your current `uv` path:
```bash
./scripts/install_team_alpha_macos.sh
```

Uninstall:
```bash
./scripts/uninstall_team_alpha_macos.sh
# or:
make app-uninstall
```

The uninstall script also stops stale app/daemon processes and clears saved app preferences, so reinstall behaves like a clean first run.

## Configuration
Use `.env.example` as the source of truth for local configuration:
```bash
cp .env.example .env
```

`flow-dictate` automatically reads `.env` from the current working directory.

Important variables for most local runs:
- `OPENAI_API_KEY`: required for `api` and `realtime` backends.
- `FLOW_DICTATE_BACKEND`: runtime backend (`stub`, `api`, or `realtime`).
- `FLOW_DICTATE_OUTPUT_MODE`: destination (`stdout`, `clipboard`, `active-app`).
- `FLOW_DICTATE_HOTKEY`: global hotkey used for hold-to-record.
- `FLOW_DICTATE_TRANSCRIPTION_MODEL`: transcription model id.

Set hotkey interactively:
```bash
uv run flow-dictate hotkey-setup
```

Additional supported variables:
- `FLOW_DICTATE_SAMPLE_RATE_HZ` (default `24000`)
- `FLOW_DICTATE_CHANNELS` (default `1`)
- `FLOW_DICTATE_AUDIO_INPUT_DEVICE` (optional)
- `FLOW_DICTATE_MAX_RECORD_SECONDS` (default `30.0`)
- `FLOW_DICTATE_OPENAI_API_KEY_ENV` (default `OPENAI_API_KEY`)
- `FLOW_DICTATE_REALTIME_WEBSOCKET_URL` (default `wss://api.openai.com/v1/realtime`)
- `FLOW_DICTATE_REALTIME_CONNECT_TIMEOUT_SECONDS` (default `15.0`)
- `FLOW_DICTATE_REALTIME_RESPONSE_TIMEOUT_SECONDS` (default `30.0`, also used as API transcription request timeout)
- `FLOW_DICTATE_ACTIVE_APP_INSERTION_STRATEGY` (default `clipboard-paste`, options: `clipboard-paste`, `direct-type`)
- `FLOW_DICTATE_ACTIVE_APP_FALLBACK_TO_CLIPBOARD` (default `true`)
- `FLOW_DICTATE_TEMP_AUDIO_DIR` (default `/tmp/flow-dictate`)
- `FLOW_DICTATE_DAEMON_POLL_INTERVAL_SECONDS` (default `0.10`)

Troubleshooting: hotkey does nothing in app mode
- Check app runtime summary in logs:
```bash
tail -f ~/Library/Logs/FlowDictate/flow-dictate-app.log
```
- Confirm you see:
  - `Effective runtime config: backend=api output_mode=active-app ...`
  - `Worker service_ready payload: backend=api output_mode=active-app ...`
- If you see `Startup: OpenAI API key is required`, open `Open Settings` and save a key.
- If hotkey is rejected, set a non-modifier expression (for example `cmd+shift+space`) in `Open Settings`.

## Project structure
```text
.
├── docs/
│   ├── architecture.md
│   ├── flow-dictate-logo.svg
│   ├── implementation-plan.md
│   ├── macos-phase-1-plan.md
│   ├── macos-phase-2-plan.md
│   ├── macos-productization-roadmap.md
│   ├── research-notes.md
│   └── testing-guide.md
├── macos/FlowDictateApp/
│   ├── Package.swift
│   └── Sources/FlowDictateApp/
├── scripts/
│   ├── install_team_alpha_macos.sh
│   └── uninstall_team_alpha_macos.sh
├── .env.example
├── src/flow_dictate/
│   ├── __main__.py
│   ├── audio.py
│   ├── cli.py
│   ├── config.py
│   ├── daemon.py
│   ├── hotkey.py
│   ├── injector.py
│   ├── interfaces.py
│   ├── permissions.py
│   ├── service.py
│   └── transcription.py
├── tests/
│   ├── test_audio.py
│   ├── test_config.py
│   ├── test_cli.py
│   ├── test_hotkey.py
│   ├── test_injector.py
│   ├── test_daemon.py
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
