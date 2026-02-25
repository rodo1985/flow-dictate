# macOS Productization Roadmap

## Goal and target persona
`flow-dictate` is moving from a terminal-first tool to a macOS desktop experience focused on people who type across many apps all day and want fast voice dictation without context switching.

Primary persona:
- A macOS knowledge worker using apps like Notes, Word, Outlook, Slack, and browser forms.
- Comfortable installing a team-alpha app, but does not want to keep a terminal window open.
- Needs clear visual feedback while recording/transcribing.

## Why Docker is out of scope
Docker is intentionally out of scope for desktop dictation UX because key capabilities are host-level macOS features:
- Global hotkeys and Input Monitoring permissions.
- Accessibility automation for direct typing/paste in the active app.
- Floating HUD/menu-bar UX over native desktop windows.

Docker remains useful for CI and isolated backend experiments, but not for day-to-day end-user dictation.

## Phase roadmap

## Phase 1: Native shell + background daemon
User value:
- Installable menu-bar app with start/stop controls and background dictation.
- No terminal needed during normal use.

In scope:
- Swift menu-bar shell (`FlowDictateApp`).
- Python daemon process (`flow-dictate daemon`) with JSONL events.
- Permission onboarding (`flow-dictate doctor --json` integration).
- Launch-at-login opt-in.
- Active-app insertion strategy: direct typing primary with automatic clipboard+Cmd+V fallback.
- Team-alpha installer/uninstaller scripts using `uv`.

Out of scope:
- App notarization/signing pipeline.
- Full settings surface and per-app policy matrix.
- Near-caret HUD positioning.

Exit criteria:
- User can install and run app from Finder.
- Worker lifecycle visible in menu bar (idle/recording/transcribing/error).
- Existing CLI workflows remain backward-compatible.

## Phase 2: Minimal floating HUD
User value:
- Immediate visual confidence while dictating in other apps.

In scope:
- Non-activating, click-through HUD.
- State-only visuals: recording, transcribing, success, error.
- Timing behavior:
  - recording visible while holding key
  - transcribing visible until completion
  - success auto-hide ~1.2s
  - error auto-hide ~3.0s
- HUD toggle in menu app settings.

Out of scope:
- Transcript text preview in HUD.
- Rich interactive mini-panel controls.
- Near-caret placement and app-specific layout tuning.

Exit criteria:
- HUD appears reliably during dictation lifecycle events.
- HUD never steals focus from active app.
- HUD recovers correctly after worker restart.

## Phase 3: Context-only future track (not implemented in this cycle)
User value:
- Polished distribution and advanced UX.

Potential scope:
- Signing/notarization and broader non-technical distribution.
- Near-caret placement heuristics.
- Expanded settings UI and per-app insertion policies.

No Phase 3 code is included in the current delivery. This section is planning context only.

## Decision log (locked)
- Swift shell + Python core.
- Team-alpha release first.
- Launch-at-login is opt-in at first run.
- Active-app insertion uses direct typing as primary strategy.
- Automatic fallback to clipboard + Cmd+V when direct typing fails.
- HUD is state-only in Phase 2.
- `uv` is required in Phase 1 install flow.

## Risks and mitigations
| Risk | Impact | Mitigation |
|---|---|---|
| Accessibility/Input Monitoring complexity | Feature appears broken | `doctor --json` onboarding + explicit remediation copy |
| App target blocks synthetic typing | Insertion failures | Built-in fallback to clipboard+Cmd+V with telemetry reason codes |
| Worker process crash | App appears unresponsive | Worker supervision with capped restart backoff |
| Toolchain/environment drift | Install friction for alpha users | Installer checks (`uv`, `swift`, Xcode CLT) and clear prerequisites |
| HUD over/under visibility issues | Poor confidence feedback | Top-center deterministic placement + non-activating panel behavior |
