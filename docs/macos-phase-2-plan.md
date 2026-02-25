# Phase 2 Implementation Plan: Floating HUD

## Objective
Add a minimal, always-available visual indicator for dictation lifecycle state while users remain focused in other macOS apps.

## Scope
Implemented Phase 2 scope in this repository:
- State-only HUD (no transcript preview).
- HUD states:
  - recording
  - transcribing
  - success
  - error
- Timing behavior:
  - recording: visible while recording
  - transcribing: visible while processing
  - success: auto-hide after ~1.2s
  - error: auto-hide after ~3.0s
- Top-center deterministic placement.
- Non-activating, click-through panel.
- Menu toggle: “Show HUD”.

Out of scope in this phase:
- Near-caret placement.
- Inline transcript snippet.
- Rich control surface (retry/cancel/settings in HUD).

## Event mapping
HUD state is driven by daemon runtime events:
- `recording_started` -> `HUDState.recording`
- `transcribing_started` -> `HUDState.transcribing`
- `insertion_succeeded` -> `HUDState.success` (auto-hide)
- `error` -> `HUDState.error` (auto-hide)

`recording_stopped` and `transcription_completed` do not render unique HUD states in Phase 2 and are used for telemetry/context only.

## Reliability controls
- HUD visibility is gated by user preference (`Show HUD`).
- App state cancels pending “return-to-idle” tasks on new events to avoid stale UI transitions.
- Worker restarts do not retain stale HUD state; app resets status to idle and re-renders from fresh event stream.

## Files introduced
- `macos/FlowDictateApp/Sources/FlowDictateApp/HUD/HUDState.swift`
- `macos/FlowDictateApp/Sources/FlowDictateApp/HUD/HUDIndicatorView.swift`
- `macos/FlowDictateApp/Sources/FlowDictateApp/HUD/HUDWindowController.swift`
- `macos/FlowDictateApp/Sources/FlowDictateApp/App/AppState.swift` (event-to-HUD mapping)

## Manual verification scenarios
1. Start worker and hold hotkey:
   - HUD shows recording indicator.
2. Release hotkey:
   - HUD switches to transcribing indicator.
3. Successful insertion:
   - HUD shows success icon then auto-hides (~1.2s).
4. Simulate runtime error:
   - HUD shows error icon then auto-hides (~3.0s).
5. Toggle “Show HUD” off:
   - HUD no longer appears for new events.
6. Toggle “Show HUD” on:
   - HUD resumes event-driven rendering.

## Acceptance checklist
- [x] HUD appears in recording/transcribing/success/error states.
- [x] HUD is non-activating and does not steal focus.
- [x] HUD auto-hide timings are implemented.
- [x] HUD setting toggle exists in menu-bar app.
- [x] HUD state remains coherent after worker restarts.

## Troubleshooting
- HUD not visible:
  - Confirm menu toggle `Show HUD` is enabled.
  - Confirm worker is running and producing daemon events.
- Worker appears active but no dictation:
  - Re-run setup and verify permissions via onboarding (`doctor --json` report).
- Text insertion fallback happening often:
  - This may indicate app-specific limitations for direct typing. Fallback to clipboard+Cmd+V is expected behavior in Phase 2.
