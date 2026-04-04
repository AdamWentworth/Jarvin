# Jarvin AI Assistant

Local, privacy-first voice assistant inspired by J.A.R.V.I.S. It runs entirely on your machine: listens, transcribes speech with Whisper, and generates replies using a local LLM. The default runtime is `llama-cpp-python`, with optional support for headless Ollama serving. No cloud APIs required.

---

## ✨ Features

- **Fully local pipeline**: mic → adaptive noise gate/VAD → Whisper STT → local LLM → optional local TTS
- **Adaptive VAD**: attack/release/hangover, pre-roll, floor tracking, min/max utterance duration
- **FastAPI service** with a mounted **Gradio** UI (`/ui`) for live monitoring and control
- **Auto-provision** of a GGUF model from Hugging Face based on hardware (configurable)
- **Conversation memory** backed by SQLite (user profile + multi-conversation history)
- **Per-device microphone selection** via HTTP API and UI
- **Host-side assistant tools** for repo search, safe command execution, weather lookups, and external-service hooks
- Clean logging, voice-triggered shutdown intents, and graceful process shutdowns

> Wake word / hotword detection and higher-quality neural TTS voices are not implemented yet.

---

## 🧱 Tech Stack

- **Backend**: FastAPI, Uvicorn
- **Speech-to-Text**: OpenAI Whisper (PyTorch)
- **LLM runtime**: embedded GGUF models via `llama-cpp-python`, with optional headless Ollama backend
- **Text-to-Speech**: `pyttsx3` (offline, OS-native voices)
- **Mic capture**: PyAudio
- **Persistence**: SQLite (user profile + conversation history)
- **Frontend**: Gradio mounted into FastAPI, with static `/_temp` for audio artifacts

---

## 📁 Project Structure

```plaintext
audio/
  mic.py
  utils.py
  wav_io.py
  vad/
    __init__.py
    detector.py
    stream.py
    utils.py

backend/
  api/
    app.py
    routes/
      audio.py
      chat.py
      control.py
      health.py
      live.py
      transcription.py
  asr/
    __init__.py
    whisper.py
  core/
    pipeline.py
    ports.py
  listener/
    __init__.py
    intents.py
    live_state.py
    loop.py
    runner.py
  llm/
    bootstrap.py
    model_manager.py
    runtime_llama_cpp.py
    runtime_local.py
  middleware/
    graceful_cancel.py
  tts/
    engine.py
  util/
    hw_detect.py
    logging_setup.py
    paths.py
  ai_engine.py
  main.py

config.py
memory/
  conversation.py
requirements.txt
server.py
scripts/
  record_and_transcribe.py
  list-mics.py
  list_mics_safe.py
ui/
  app.py
  actions.py
  api.py
  components.py
  handlers.py
  poller.py
  styles.py
models/                 # GGUF models (auto-provisioned here)
temp/                   # ephemeral audio / TTS chunks
tests/                  # pytest suite
README.md
.python-version
pyproject.toml
```

## ⚙️ Configuration

Edit `config.py` or override via env vars (prefix **`JARVIN_`**, case-insensitive). Common examples:

```bash
# Server / UI
JARVIN_SERVER_HOST=0.0.0.0
JARVIN_SERVER_PORT=8000
JARVIN_START_LISTENER_ON_BOOT=true
JARVIN_GRADIO_MOUNT_PATH=/ui
JARVIN_GRADIO_AUTO_OPEN=true
JARVIN_GRADIO_OPEN_DELAY_SEC=1.0
JARVIN_CORS_ALLOW_ORIGINS='["http://localhost:3000"]'

# Audio / temp
JARVIN_SAMPLE_RATE=16000
JARVIN_CHUNK=1024
JARVIN_RECORD_SECONDS=5
JARVIN_AMP_FACTOR=10.0
JARVIN_TEMP_DIR=./temp

# Whisper STT
# one of: tiny | base | small | medium | large | unset for auto
JARVIN_WHISPER_MODEL_SIZE=small

# VAD / noise gate (see config.py for full list)
JARVIN_VAD_CALIBRATION_SEC=1.5
JARVIN_VAD_THRESHOLD_MULT=3.0
JARVIN_VAD_THRESHOLD_ABS=200
JARVIN_VAD_ATTACK_MS=120
JARVIN_VAD_RELEASE_MS=350
JARVIN_VAD_HANGOVER_MS=200
JARVIN_VAD_PRE_ROLL_MS=300

# LLM
JARVIN_MODELS_DIR=models
JARVIN_LLM_BACKEND=llama_cpp
JARVIN_LLM_AUTO_PROVISION=true
JARVIN_LLM_FORCE_LOGICAL_NAME=phi-3-mini-4k-instruct
JARVIN_LLM_FLAT_LAYOUT=true
JARVIN_LLM_CLEAN_VENDOR_DIRS=true
JARVIN_LLM_N_THREADS=8
JARVIN_LLM_N_GPU_LAYERS=-1  # offload all possible layers to GPU
JARVIN_LLM_VERBOSE=true
JARVIN_LLM_LOG_SYSTEM_INFO=true
JARVIN_LLM_REQUIRE_GPU=false

# Optional headless Ollama backend
JARVIN_OLLAMA_BASE_URL=http://127.0.0.1:11434
JARVIN_OLLAMA_MODEL=

# Persistence (SQLite-backed profile + conversations)
JARVIN_DATA_DIR=./data
JARVIN_DB_FILENAME=jarvin.sqlite3
JARVIN_DB_WAL=true
```

---

## 🚀 Quick Start

If you change or uninstall the base Python used to create `.venv`, recreate the virtual environment first:

```bash
py -3.11 -m venv .venv
```

1) **Install dependencies**

    ```bash
    .\.venv\Scripts\python -m pip install -r requirements.txt
    ```

    For Windows + NVIDIA GPU, use the CUDA-enabled Torch install we verified in this repo:

    ```bash
    .\.venv\Scripts\python -m pip install -r requirements-gpu-cu128.txt
    ```

    Then run the GPU diagnostics:

    ```bash
    .\.venv\Scripts\python scripts/diagnose_gpu.py
    ```

    On this machine, plain `pip install torch` produced a CPU-only wheel. The GPU requirements file avoids that and also pulls the official Windows CUDA wheel for `llama-cpp-python`.

2) **Editable install (required for tests)**  
   Makes `backend`, `audio`, and `ui` importable as installed packages.  
   The pytest suite expects this layout.

   ```bash
   .\.venv\Scripts\python -m pip install -e .
   ```

3) **Run the server (FastAPI + Gradio UI)**

    ```bash
    python server.py
    ```

    If `.venv` exists and you launch `server.py` from a different Python, Jarvin will re-run itself under the repo venv automatically.

    API base: `http://127.0.0.1:8000`
    UI:       `http://127.0.0.1:8000/ui`   (auto-opens if JARVIN_GRADIO_AUTO_OPEN=true)

4) **Talk**  
   Jarvin auto-calibrates the mic, records short utterances, runs Whisper → LLM, and shows transcript & reply in the UI.

    Tips:
      - Check OS microphone permissions if nothing is captured.
      - Env overrides use the JARVIN_prefix (e.g., JARVIN_LOG_LEVEL=debug).
      - First run may auto-download a GGUF model into models/.

---

## 🧪 Testing

Jarvin uses [pytest](https://docs.pytest.org/) for the test suite.

---

- Make sure you've rerformed an editable install first

```bash
python -m pip install -e .
```

- Run all tests from the project root:

```bash
pytest
```

## 🧪 One-Off Transcription Test (CLI)

Record and transcribe in a loop:

```bash
python scripts/record_and_transcribe.py
```

---

## 🧰 Troubleshooting

### Whisper / PyTorch

If `python scripts/diagnose_gpu.py` reports `torch ... +cpu`, you installed a CPU-only wheel. Reinstall the CUDA build:

```bash
pip install --upgrade --force-reinstall torch==2.7.1+cu128 --index-url https://download.pytorch.org/whl/cu128
```

### Microphone (PyAudio)

- Check Windows **Privacy & security → Microphone** permissions.  
- If “No input devices found”, verify the device in Sound Settings.  
- If transcripts are empty, lower `RECORD_SECONDS`, tweak `AMP_FACTOR`, and ensure mic levels are adequate.

### ffmpeg errors

- The live loop **does not call ffmpeg** (raw PCM).  
- If you still see ffmpeg errors, confirm your `audio/speech_recognition.py` matches the current version.

### NVIDIA GPU checklist

- Jarvin now primes common CUDA DLL directories before importing `llama-cpp-python`.
- Use `python scripts/diagnose_gpu.py` to verify both Torch and `llama-cpp-python`.
- Set `JARVIN_LLM_N_GPU_LAYERS=-1` to request full GPU offload and `JARVIN_LLM_REQUIRE_GPU=true` if you want startup to fail when GPU offload is unavailable.

## llama.cpp on Windows

See the NVIDIA GPU checklist above for the current Windows GPU path.

Jarvin can also use a headless Ollama backend if you want a separate inference service process while keeping Jarvin's own UI and behavior.

Example:

```powershell
$env:JARVIN_LLM_BACKEND = "ollama_http"
$env:JARVIN_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
$env:JARVIN_OLLAMA_MODEL = "your-model-tag"
python server.py
```

Jarvin will not auto-pull Ollama models for you.
Provision the model yourself on the host machine if you use this backend.

- Prefer **Conda** binaries to avoid compiling `llama-cpp-python`.  
- If you compiled and it's slow, ensure it’s a **CPU build** (no GPU expected on this laptop) and that `n_threads` is sensible (auto by default).

---

## 🔒 Privacy

All audio and text stay on your machine. No external AI APIs are called during normal operation.  
(Models are fetched once from Hugging Face during setup if auto-provision is enabled.)

---

## 🧠 Persistence & conversations

Jarvin stores profile and conversation state in a local SQLite database:

- The DB path is derived from `JARVIN_DATA_DIR` and `JARVIN_DB_FILENAME`
  (defaults to `./data/jarvin.sqlite3`).
- The Gradio UI exposes a **Conversations** panel where you can:
  - switch between conversations,
  - rename or delete them (with safeguards),
  - clear the history for the active conversation.
- Conversation and profile data never leave your machine.

To reset all memory, delete the SQLite file or use the UI to clear conversations.

---

## 📜 API & Scripts

### HTTP API

- `GET /healthz` – liveness/readiness probe
- `GET /status` – background listener status
- `POST /start` / `POST /stop` – control the background listener
- `POST /shutdown` – terminate FastAPI + UI process (graceful, with Windows failsafe)
- `GET /live` – latest transcript/reply, timing metrics, and flags (`recording`, `processing`), plus TTS URL
- `POST /transcribe` – one-off file transcription (multipart upload)
- `POST /chat` – stateless chat via local LLM, with optional profile/history context
- `GET /agent/tools` – list the enabled host-side tool commands and capabilities
- `POST /agent/tools/list` – list files under the configured workspace root
- `POST /agent/tools/search` – repo text search
- `POST /agent/tools/read` – read a file snippet
- `POST /agent/tools/write` – write or append a file under the workspace root
- `POST /agent/tools/run` – run an allowlisted local command
- `GET /audio/devices` – list input-capable audio devices and current selection
- `POST /audio/select` – validate/select input device, optionally restart listener

### Chat Tool Commands

Jarvin can also execute explicit host-side assistant actions from chat when you start a message with `/tool`:

- `/tool help`
- `/tool ls backend`
- `/tool search llm_backend`
- `/tool read backend/api/app.py 1 80`
- `/tool run git status`
- `/tool weather Seattle`
- `/tool web local llama cpp docs`
- `/tool calendar 7`

Weather works immediately with Open-Meteo.

Google Calendar requires an OAuth desktop client JSON saved at `secrets/google-calendar-client.json`, then run:

```text
/tool calendar auth
```

Google web search is only available if the host is configured with legacy Programmable Search / Custom Search JSON API credentials. Otherwise use `/tool web ...` with the default provider.

### Scripts

- `scripts/record_and_transcribe.py` – CLI loop for quick ASR testing
- `scripts/list-mics.py` – list working input devices at 16 kHz mono
- `scripts/list_mics_safe.py` – enumerate input devices without opening streams

---

## 🗺️ Roadmap

- Wake-word / hotword detection
- Richer conversation tools (naming, tagging, export)
- Higher-quality neural TTS voices (e.g. Piper) and voice selection
- Hot-swappable LLM models and runtime tuning from the UI
- Optional tool integrations (web search, filesystem tools, etc.) while keeping offline-first by default

---
