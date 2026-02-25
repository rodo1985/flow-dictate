# Testing Guide

This guide documents how to validate `flow-dictate` after local changes.

## 1) Automated checks

## Run unit tests
```bash
uv run --group dev pytest
```

## Run lint checks
```bash
uv run --group dev ruff check .
```

## 2) Quick CLI smoke tests

## Permission preflight
```bash
uv run flow-dictate doctor
uv run flow-dictate doctor --prompt-permissions
uv run flow-dictate doctor --json
```

Expected behavior:
- Exit code `0` when all required permissions are granted.
- Exit code `1` when one or more permissions still need action.

## Interactive hotkey setup
```bash
uv run flow-dictate hotkey-setup
```

Expected behavior:
- CLI prompts for a key chord.
- Releasing the keys writes `FLOW_DICTATE_HOTKEY=...` to `.env`.

## Stub backend run (deterministic)
```bash
uv run flow-dictate run --backend stub --run-once --simulate-trigger --use-stub-hotkey
```

Expected behavior:
- Command exits successfully.
- A stub transcript is produced and routed to the selected output mode.

## Daemon event stream dry run
```bash
uv run flow-dictate daemon --backend stub --run-once --simulate-trigger --use-stub-hotkey
```

Expected behavior:
- Command exits successfully.
- Stdout emits newline-delimited JSON events (service lifecycle + insertion outcome).

## 3) Output mode verification

## Stdout
```bash
uv run flow-dictate run --backend stub --run-once --simulate-trigger --output stdout
```

Expected behavior:
- Transcript text is printed in terminal output.

## Clipboard
```bash
uv run flow-dictate run --backend stub --run-once --simulate-trigger --output clipboard
pbpaste
```

Expected behavior:
- `pbpaste` returns the dictated transcript.

## Active app (with fallback)
```bash
uv run flow-dictate run --backend stub --run-once --simulate-trigger --output active-app
```

Expected behavior:
- If permissions allow automation: text is pasted in the active app.
- If paste automation fails: text remains in clipboard and warning is shown.

## 4) API backend verification

## Preconditions
- macOS microphone permission granted for the terminal app.
- OpenAI API key present in `.env` as `OPENAI_API_KEY` (or custom env var configured via `FLOW_DICTATE_OPENAI_API_KEY_ENV`).

## Run API hold-to-record flow
```bash
uv run flow-dictate run --backend api --output stdout
```

Expected behavior:
- Press and hold the configured hotkey to begin recording.
- Terminal shows a "Recording..." indicator while key is held.
- Releasing the hotkey stops recording.
- A transcript is returned from OpenAI Audio API and printed to stdout.

## 5) Environment-variable checks

## Backend and output defaults from env
```bash
cat <<'EOF' > .env
FLOW_DICTATE_BACKEND=stub
FLOW_DICTATE_OUTPUT_MODE=clipboard
EOF
uv run flow-dictate run --run-once --simulate-trigger --use-stub-hotkey
```

Expected behavior:
- CLI uses `.env` defaults when `--backend` and `--output` are omitted.

## Optional realtime verification
```bash
uv run flow-dictate run --backend realtime --output stdout
```

Expected behavior:
- Same hold-to-record UX as API backend.
- If the selected model is unsupported in realtime mode, the command exits with a startup or runtime error.

## 7) macOS app shell checks (team-alpha)

## Build app shell
```bash
swift build --package-path macos/FlowDictateApp
```

Expected behavior:
- Swift package compiles cleanly.

## Installer smoke test
```bash
./scripts/install_team_alpha_macos.sh
open /Applications/FlowDictate.app
```

Expected behavior:
- App opens as a menu-bar utility.
- Flow Dictate icon is visible in the macOS menu bar.
- Setup window can be opened from menu and auto-opens when required permissions are missing.
- Settings window can be opened from menu (`Open Settings`).
- Setup includes a `Request Permissions` action that opens the next missing permission pane.
- Setup includes direct buttons for Microphone, Accessibility, and Input Monitoring panes.
- When Microphone is missing, `Request Permissions` also triggers direct microphone access request from the app.
- Starting worker surfaces lifecycle states in menu.

## App settings workflow checks
1. Open `Open Settings` from the menu bar.
2. Save a valid hotkey and API key.
3. Confirm worker restarts automatically.
4. Clear API key and verify worker start is blocked with actionable error.

Expected behavior:
- App mode uses Keychain + app settings as runtime source for API key/hotkey.
- App runtime is forced to backend `api` + output mode `active-app`.
- Worker start is blocked when API key is missing.

## HUD smoke test
- Enable `Show HUD` in menu.
- Trigger dictation hotkey in a text field.

Expected behavior:
- HUD appears for recording and transcribing.
- Success/error states auto-hide after configured timings.

## App log smoke test
- In the menu-bar app, click `Open Logs`.
- Confirm log file exists at `~/Library/Logs/FlowDictate/flow-dictate-app.log`.
- Trigger dictation once and verify new `worker event` lines appear.

Expected log signatures:
- Startup config:
  - `Effective runtime config: backend=api output_mode=active-app insertion_strategy=direct-type hotkey=... key_present=true|false`
- Worker launch summary:
  - `Starting worker with cwd=... backend=api output_mode=active-app insertion_strategy=direct-type hotkey=... key_present=true`
- Daemon ready payload:
  - `Worker service_ready payload: backend=... output_mode=... insertion_strategy=... hotkey=... config_source=...`
- Blocked startup:
  - `Skipping worker start because required settings are missing/invalid: ...`

## 6) Useful failure signatures
- `flow-dictate startup error: ... OPENAI_API_KEY ... required`: set API key or use `--backend stub`.
- `Unable to start global hotkey listener`: run `flow-dictate doctor` and grant Input Monitoring.
- `Active-app output is only supported on macOS`: expected when run outside macOS.
- `env: uv: No such file or directory` in app logs: rerun `./scripts/install_team_alpha_macos.sh` so the launcher refreshes `FLOW_DICTATE_UV_BIN`.
- App exits when requesting microphone permission: reinstall via `./scripts/install_team_alpha_macos.sh` to refresh app bundle privacy usage strings.
