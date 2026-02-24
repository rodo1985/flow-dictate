# Implementation Plan: macOS Voice Dictation CLI

## 1) Objective
Ship an MVP for a **macOS-only** dictation CLI with:
- Fast streaming transcription
- Optional rewrite presets
- Output to stdout, clipboard, or active app
- Reliable permission checks and failure recovery

## Current implementation status (February 24, 2026)
- Foundation scaffold is complete (`pyproject`, package layout, CLI, service orchestration, tests).
- Real backend prototype is implemented for:
  - microphone capture (`MicrophoneAudioCapture`)
  - OpenAI Realtime transcription over websocket (`OpenAIRealtimeTranscriptionClient`)
- Stub backend remains available for deterministic local development and CI tests.

## 2) Assumptions and Constraints
- Python project managed with `uv`.
- OpenAI API is the initial backend.
- No full desktop GUI in MVP (CLI-first).
- macOS 13+ target, Apple Silicon and Intel supported.

## 3) MVP Release Roadmap (Phased)

## Phase 0: Foundation (Day 1-2)
Deliverables:
- `src/` package scaffold and CLI entrypoint.
- Config loader (`.env` + optional user config).
- `doctor` command with basic environment checks.

Exit criteria:
- `uv run flow-dictate --help` works.
- `uv run flow-dictate doctor` reports missing/valid config clearly.

## Phase 1: Audio + Streaming Transcript (Day 3-6)
Deliverables:
- Mic capture pipeline and device selection.
- Streaming ASR client with partial/final transcript events.
- Transcript assembler with deterministic merge behavior.

Exit criteria:
- Dictating short speech returns final text reliably.
- Partial output appears during speech with acceptable latency.

## Phase 2: Output + Permissions (Day 7-9)
Deliverables:
- Output router: `stdout`, `clipboard`, `active-app`.
- macOS permission preflight checks and user guidance.
- Hotkey or hold-to-record workflow.

Exit criteria:
- Output modes work independently.
- Permission-denied cases fail gracefully with actionable instructions.

## Phase 3: Rewrite + Reliability (Day 10-12)
Deliverables:
- Rewrite presets (`clarity`, `concise`, `formal`).
- Retries/timeouts for network and API failures.
- Structured logs + latency/error metrics.

Exit criteria:
- Rewrite is optional and does not block base dictation path.
- Known failures map to clear error codes and messages.

## Phase 4: MVP Hardening + Release (Day 13-15)
Deliverables:
- End-to-end tests for key workflows.
- README/docs updates and usage examples.
- Versioned MVP tag and release notes.

Exit criteria:
- CI green for tests/lint.
- Fresh-machine setup and quickstart validated.

## 4) Multi-Agent Parallel Task Breakdown
Use this plan when multiple contributors/agents implement in parallel.

| Agent | Scope | Parallelizable? | Depends On | Output |
|---|---|---|---|---|
| Agent A: CLI + Config | CLI commands, settings model, `.env` loading, `doctor` skeleton | Yes | None | Stable command surface + config contract |
| Agent B: Audio Core | Device enumeration, capture loop, frame buffering, VAD integration | Yes | Minimal from A (config keys) | Audio module + unit tests |
| Agent C: ASR Streaming | API client, partial/final events, retry/timeout policy | Yes | Minimal from A (API config) | Streaming transcription module |
| Agent D: Output + macOS Integration | Clipboard/active-app output, permission checks, fallback behavior | Yes | A for config + command flags | Output router + permission helper |
| Agent E: Rewrite + Prompting | Rewrite presets, prompt templates, post-processing | Yes | C (transcript output schema) | Rewrite module + tests |
| Agent F: QA + Observability | Structured logging, metrics, integration tests, failure matrix validation | Partial | B/C/D/E integration points | Test suite + reliability report |
| Agent G: Docs/Release | README, docs, release checklist/changelog | Yes | Inputs from all agents | Contributor-ready docs + release notes |

Suggested integration order:
1. Merge A first (command/config contracts).
2. Merge B + C in parallel, then integration test dictation path.
3. Merge D (output + permissions).
4. Merge E (optional rewrite path).
5. Merge F (hardening) and G (final docs/release).

## 5) Work Items by Track

## Core Track
- Build a stable event model: `audio_chunk`, `partial_text`, `final_text`, `rewrite_text`, `error`.
- Keep modules decoupled through typed interfaces.
- Add deterministic tests for transcript merge edge cases.

## Reliability Track
- Implement retry with capped exponential backoff.
- Add command-level timeout controls.
- Define error code catalog (e.g., `E_MIC_001`, `E_API_002`, `E_PERM_003`).

## UX Track
- Real-time status in CLI (recording, processing, done).
- Clear output mode selection and confirmation.
- Human-readable remediation steps on failure.

## 6) Test Plan (MVP Minimum)
- Unit tests:
  - Config parsing and validation.
  - Transcript merge logic.
  - Rewrite preset formatting.
- Integration tests:
  - Mocked ASR streaming path with partial/final events.
  - Output routing behavior for each target.
  - Permission-denied and network-failure scenarios.
- Manual smoke tests on macOS:
  - Built-in mic and external mic.
  - Active app insertion in at least two target apps.

Example commands:
```bash
uv run pytest
uv run pytest -k "transcript or output"
uv run flow-dictate doctor
uv run flow-dictate dictate --ptt --output stdout
```

## 7) Risks and Mitigations
| Risk | Impact | Mitigation |
|---|---|---|
| macOS permission complexity | Feature appears broken to users | Preflight checks + explicit setup docs |
| API latency variability | Poor real-time experience | Stream partials early; make rewrite optional |
| Hotkey conflicts / event tap instability | Inconsistent recording start/stop | Configurable hotkey + fallback CLI mode |
| Regression in merge logic | Corrupted transcript output | Golden tests with varied speech patterns |

## 8) Definition of Done (MVP)
- Fresh setup works with documented `uv` commands.
- Dictation works end-to-end on macOS with streaming feedback.
- Rewrite can be enabled/disabled via CLI flag.
- Output works for stdout and clipboard; active-app path has permission-aware fallback.
- Tests pass locally and in CI.
- Architecture and implementation docs are current and contributor-friendly.
