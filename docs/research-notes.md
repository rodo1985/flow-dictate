# Research Notes (February 24, 2026)

## Scope
This note captures product and API research used to shape the MVP design for `flow-dictate`.

## Product signals from WhisperFlow/Wispr Flow
- The product behavior we want to emulate is best represented by **Wispr Flow** on macOS:
  press/hold a trigger, speak naturally, receive fast dictation, and insert text in many apps.
- The documentation describes a default trigger (`fn`) and configurable shortcuts.
- The product surfaces a small floating "Flow Bar" near the typing context instead of a full UI.
- Setup emphasizes permission enablement on macOS (microphone and accessibility) before first use.
- Product modes include direct dictation and rewrite-style transformations for tone/format.

Sources:
- [wisprflow.ai](https://wisprflow.ai/)
- [Keyboard shortcuts (Wispr Flow docs)](https://docs.wisprflow.ai/en/articles/11799203-keyboard-shortcuts)
- [Troubleshooting transcription (Flow Bar + behavior)](https://docs.wisprflow.ai/en/articles/11605184-troubleshooting-transcription-issues-in-wispr-flow)
- [How to enable flow mode](https://docs.wisprflow.ai/en/articles/11754474-how-to-enable-flow-mode)
- [Compatibility and permissions guidance](https://docs.wisprflow.ai/en/articles/11887200-why-isn-t-wispr-flow-working-on-certain-apps)

## OpenAI API signals (speech and realtime)
- OpenAI supports both:
  - `audio/transcriptions` for file/chunk transcription workflows.
  - Realtime transcription sessions for low-latency streaming over WebSocket.
- Realtime transcription sessions support audio formats including PCM, G.711 u-law, and G.711 a-law.
- Realtime transcription configuration includes model, optional language hint, prompt guidance, and turn detection.
- Current transcription model options in references include `gpt-4o-transcribe`, `gpt-4o-mini-transcribe`, and `whisper-1` variants.
- Realtime docs note that model-native audio interpretation and asynchronous transcription output can differ slightly, so transcript handling should be robust.

Sources:
- [Create transcription session (API reference)](https://developers.openai.com/api/reference/resources/realtime/subresources/transcription_sessions/methods/create/)
- [Realtime transcription guide (platform docs)](https://platform.openai.com/docs/guides/realtime-transcription)
- [Speech-to-text guide (platform docs)](https://platform.openai.com/docs/guides/speech-to-text)
- [Audio transcriptions endpoint (platform docs)](https://platform.openai.com/docs/api-reference/audio/createTranscription)

## Design implications for this repo
- Build a macOS-only CLI daemon with a pluggable architecture:
  hotkey listener, capture engine, transcription client, and output router.
- Phase delivery:
  1. reliable hold-to-dictate + final transcript insertion
  2. low-latency partial transcript streaming
  3. optional rewrite presets
- Include `doctor` preflight checks early for permissions and environment readiness.
- Keep output fallback options (`active-app` -> clipboard -> stdout) to avoid blocking user workflows.
