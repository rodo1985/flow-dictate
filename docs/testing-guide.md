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
```

Expected behavior:
- Exit code `0` when all required permissions are granted.
- Exit code `1` when one or more permissions still need action.

## Stub backend run (deterministic)
```bash
uv run flow-dictate run --backend stub --run-once --simulate-trigger --use-stub-hotkey
```

Expected behavior:
- Command exits successfully.
- A stub transcript is produced and routed to the selected output mode.

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

## 4) Realtime backend verification

## Preconditions
- macOS microphone permission granted for the terminal app.
- OpenAI API key available in `OPENAI_API_KEY` (or custom env var configured via `FLOW_DICTATE_OPENAI_API_KEY_ENV`).

## Run one realtime cycle
```bash
export OPENAI_API_KEY="your_key_here"
uv run flow-dictate run --backend realtime --run-once --simulate-trigger --use-stub-hotkey --output stdout
```

Expected behavior:
- Microphone capture starts and stops for one cycle.
- A transcript is returned from OpenAI Realtime and printed to stdout.

## 5) Environment-variable checks

## Backend and output defaults from env
```bash
export FLOW_DICTATE_BACKEND=realtime
export FLOW_DICTATE_OUTPUT_MODE=clipboard
uv run flow-dictate run --run-once --simulate-trigger --use-stub-hotkey
```

Expected behavior:
- CLI uses env defaults when `--backend` and `--output` are omitted.

## 6) Useful failure signatures
- `flow-dictate startup error: ... OPENAI_API_KEY ... required`: set API key or use `--backend stub`.
- `Unable to start global hotkey listener`: run `flow-dictate doctor` and grant Input Monitoring.
- `Active-app output is only supported on macOS`: expected when run outside macOS.
