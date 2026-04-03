# Jarvin Change Checklist

Use this as a lightweight close-out checklist after edits.

## Always

- Run from repo root.
- Check `git status --short` before and after edits.
- Prefer targeted verification over no verification.

## If You Touched Startup Or Environment

- Run:

```powershell
.\.venv\Scripts\python -m pytest tests\test_server_launcher.py -q
```

- Sanity check:

```powershell
python server.py
```

Stop it after confirming startup if you do not need a full manual session.

## If You Touched GPU / Model Loading

- Run:

```powershell
.\.venv\Scripts\python scripts\diagnose_gpu.py
.\.venv\Scripts\python -m pytest tests\backend\llm\test_runtime_llama_cpp.py tests\backend\util\test_hw_detect.py -q
```

- Confirm:
  - Torch sees CUDA
  - `llama-cpp-python` imports
  - diagnostics mention the NVIDIA device

## If You Touched Whisper / Audio / Listener Flow

- Run:

```powershell
.\.venv\Scripts\python -m pytest tests\audio\test_audio_components.py tests\backend\listener\test_intents.py -q
```

- Re-check `backend/core/pipeline.py` and `backend/listener/runner.py` together so turn persistence is not duplicated.

## If You Touched Persistence Or Conversation Flow

- Run:

```powershell
.\.venv\Scripts\python -m pytest tests\memory\test_conversation.py tests\backend\api\test_chat_endpoint.py -q
```

- Be careful with schema changes; prefer migration-safe additions.

## If You Touched Config Or Defaults

- Run:

```powershell
.\.venv\Scripts\python -m pytest tests\config\test_settings.py -q
```

## If You Touched UI Or API Wiring

- Run:

```powershell
.\.venv\Scripts\python -m pytest tests\backend\api\test_health_status.py tests\backend\middleware\test_graceful_cancel.py -q
```

- Then do a quick manual pass in the browser if the change is visible in `/ui`.
