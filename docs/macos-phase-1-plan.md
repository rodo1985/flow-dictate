# Phase 1 Implementation Plan: Service + Menu Bar App

## Objective
Deliver a team-alpha macOS menu-bar experience that runs dictation in the background and removes the terminal from day-to-day usage.

## Architecture
- Python remains source-of-truth for hotkey, audio, transcription, and insertion.
- New daemon command emits JSONL runtime events consumed by the app shell.
- Swift app handles:
  - menu-bar UX and status rendering
  - onboarding and permission report display
  - launch-at-login opt-in
  - worker process supervision

## Implemented components

## Python daemon track
- Added `flow-dictate daemon` command for app-shell integration.
- Added daemon runtime event model and writer:
  - `service_ready`
  - `recording_started`
  - `recording_stopped` (`elapsed_seconds`)
  - `transcribing_started`
  - `transcription_completed` (`character_count`)
  - `insertion_succeeded` (`method`)
  - `insertion_fallback_used` (`reason`)
  - `error` (`code`, `message`)
- Added stable daemon error-code mapping:
  - `E_DAEMON_CONFIG_001`
  - `E_DAEMON_RUNTIME_001`
  - `E_DAEMON_UNKNOWN_001`
- Added callback hooks in `DictationService` for transcription/insertion lifecycle events.

## CLI onboarding track
- Added `flow-dictate doctor --json` for machine-readable permission preflight.
- JSON shape includes:
  - `all_required_granted`
  - `microphone`
  - `accessibility`
  - `input_monitoring`

## Active-app insertion strategy track
- Added `FLOW_DICTATE_ACTIVE_APP_INSERTION_STRATEGY`.
- Supported values:
  - `clipboard-paste` (default, backward-compatible)
  - `direct-type`
- Added structured `InjectionResult` metadata for fallback telemetry.
- Direct-typing strategy now auto-falls back to clipboard+Cmd+V when enabled.

## Swift shell track (`macos/FlowDictateApp`)
- Added menu-bar app with:
  - worker status states (`idle`, `recording`, `transcribing`, `error`)
  - start/stop worker actions
  - launch-at-login toggle
  - HUD toggle
  - setup and permissions actions
- Added onboarding window:
  - pulls permission report from `doctor --json`
  - supports launch-at-login opt-in
  - links to macOS Privacy settings
- Added worker manager:
  - starts daemon with explicit cwd/env
  - parses daemon JSONL stream
  - restart with capped exponential-style backoff

## Install track (team-alpha)
- Added installer script:
  - `scripts/install_team_alpha_macos.sh`
  - checks prerequisites (`uv`, `swift`, Xcode CLT)
  - syncs dependencies with `uv`
  - builds app shell
  - creates app bundle in `/Applications/FlowDictate.app`
- Added uninstaller:
  - `scripts/uninstall_team_alpha_macos.sh`

## Public interfaces introduced/updated
- CLI:
  - `flow-dictate daemon`
  - `flow-dictate doctor --json`
- Config:
  - `FLOW_DICTATE_ACTIVE_APP_INSERTION_STRATEGY`
- Runtime event contract:
  - JSONL schema documented above
- Text injection:
  - structured result (`inserted`, `method`, `fallback_used`, `fallback_reason`)

## Team-alpha runbook
1. Install app shell:
```bash
./scripts/install_team_alpha_macos.sh
```
2. Launch app:
```bash
open /Applications/FlowDictate.app
```
3. Confirm the Flow Dictate icon appears in the macOS menu bar.
4. Open setup and grant required permissions.
5. Enable launch-at-login if desired.
6. Start worker from menu-bar menu.

Notes:
- Setup opens automatically if required permissions are missing.
- `scripts/uninstall_team_alpha_macos.sh` removes the app bundle, stops stale app/daemon processes, and clears saved app preferences for a clean reinstall.

## Acceptance checklist
- [x] Team-alpha installer and uninstaller scripts exist.
- [x] Daemon JSONL event stream implemented.
- [x] Menu-bar shell integrates with daemon stream.
- [x] Permission onboarding can consume `doctor --json`.
- [x] Direct typing primary + auto fallback path implemented.
- [x] Existing CLI behavior preserved for `run`, `doctor`, and `hotkey-setup`.

## Validation commands
Python:
```bash
uv run --group dev pytest
uv run --group dev ruff check .
```

Swift:
```bash
swift build --package-path macos/FlowDictateApp
```

Note:
- `swift test --package-path macos/FlowDictateApp` may fail in constrained environments where test runtime modules are unavailable. Use `swift build` plus manual app smoke tests for team-alpha validation.
