# Jarvin Architecture

## Purpose

Jarvin is a local-first voice assistant for Windows. Its main runtime path is:

1. microphone capture
2. adaptive VAD / utterance detection
3. Whisper transcription
4. local GGUF LLM reply generation
5. optional local TTS
6. FastAPI + Gradio display / control

Normal operation is intended to stay on-device. Models may be downloaded once during setup, but regular inference does not call cloud APIs.

## Startup Flow

1. `python server.py` starts the app from repo root.
2. [`server.py`](../server.py) re-launches itself under the repo `.venv` if needed, then builds the FastAPI app and mounted Gradio UI.
3. [`backend/api/app.py`](../backend/api/app.py) handles lifespan startup:
   - creates `app.state.stop_event`
   - auto-provisions / loads the local LLM if enabled
   - starts the background listener task if `start_listener_on_boot` is true
4. The listener task in [`backend/listener/runner.py`](../backend/listener/runner.py):
   - creates the cached Whisper ASR object
   - opens the selected mic device
   - calibrates the VAD
   - loops on utterances and forwards each one to the processing pipeline

## Main Runtime Path

### Audio Capture

- [`audio/vad/`](../audio/vad) contains the streaming VAD implementation.
- [`backend/listener/loop.py`](../backend/listener/loop.py) wraps the VAD into a simple blocking API that the async runner can call via `asyncio.to_thread`.

### Utterance Processing

- [`backend/core/pipeline.py`](../backend/core/pipeline.py) is the core turn-processing function.
- In the hot path, it runs ASR from in-memory PCM, builds short context from saved profile + recent turns, asks the local LLM for a reply, persists the turn, and optionally synthesizes TTS.
- It still writes a temp WAV for playback/debug state, but Whisper no longer depends on that file round-trip.

### ASR

- [`backend/asr/whisper.py`](../backend/asr/whisper.py) owns Whisper model caching and device selection.
- GPU is preferred automatically when CUDA is available.
- The current implementation keeps LayerNorm in fp32 on CUDA to avoid mixed-precision errors seen on some Torch / Whisper combinations.
- The listener path can now transcribe normalized in-memory PCM directly, which avoids a temporary WAV dependency on every turn.

### LLM

- [`backend/llm/model_manager.py`](../backend/llm/model_manager.py) chooses and downloads the GGUF model.
- [`backend/llm/runtime_llama_cpp.py`](../backend/llm/runtime_llama_cpp.py) owns the cached `llama-cpp-python` runtime.
- [`backend/util/windows_dll.py`](../backend/util/windows_dll.py) primes Windows DLL search paths so CUDA-backed `llama-cpp-python` wheels can find the runtime libraries they need.

### UI and Live State

- [`backend/listener/live_state.py`](../backend/listener/live_state.py) is the shared in-memory state between the listener and the UI/API.
- [`ui/app.py`](../ui/app.py) builds the Gradio app.
- The UI uses polling and a sequence-based update model so transcript/reply rendering only advances when a new utterance snapshot is published.

## Persistence

- [`memory/conversation.py`](../memory/conversation.py) owns the SQLite connection, migrations, active conversation tracking, history, and user profile state.
- The database lives under `data/` by default and is configured via [`config.py`](../config.py).
- Conversation history is now multi-conversation, with the active conversation tracked in `app_state`.

## Important Invariants

- `process_utterance()` persists turns. The listener must not append the same turns again.
- `set_snapshot()` is what advances the live sequence number. `set_status()` updates flags without creating a new turn event.
- The repo is Windows-first right now. GPU setup assumes the Windows CUDA wheel path documented in `requirements-gpu-cu128.txt`.
- Keep the app local-first unless there is a deliberate product decision to add networked tools.
- Prefer additive schema changes in `memory/conversation.py`; users may already have local data.

## Key Files To Know

- [`server.py`](../server.py): startup entrypoint and `.venv` auto-launch behavior
- [`config.py`](../config.py): global settings and env-driven knobs
- [`backend/api/app.py`](../backend/api/app.py): FastAPI lifespan and router composition
- [`backend/listener/runner.py`](../backend/listener/runner.py): background audio loop orchestration
- [`backend/core/pipeline.py`](../backend/core/pipeline.py): one utterance in, one turn out
- [`backend/asr/whisper.py`](../backend/asr/whisper.py): Whisper device/runtime behavior
- [`backend/llm/runtime_llama_cpp.py`](../backend/llm/runtime_llama_cpp.py): llama.cpp runtime loading and GPU handling
- [`memory/conversation.py`](../memory/conversation.py): SQLite persistence and conversation state
- [`ui/app.py`](../ui/app.py): Gradio app assembly
