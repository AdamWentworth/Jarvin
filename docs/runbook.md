# Jarvin Runbook

## Environment

- Run commands from repo root.
- Use Python 3.11 for the project venv.
- If the base Python installation changes, recreate `.venv`.

## Create Or Recreate The Venv

```powershell
py -3.11 -m venv .venv
```

## Install Dependencies

CPU / general path:

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m pip install -e .
```

Windows + NVIDIA GPU path:

```powershell
.\.venv\Scripts\python -m pip install -r requirements-gpu-cu128.txt
.\.venv\Scripts\python -m pip install -e .
```

## Optional Headless Ollama Backend

Jarvin can use Ollama as an inference service without using any Ollama UI.
Jarvin still owns the app UI, prompts, and behavior.

Example env overrides:

```powershell
$env:JARVIN_LLM_BACKEND = "ollama_http"
$env:JARVIN_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
$env:JARVIN_OLLAMA_MODEL = "your-model-tag"
```

Notes:

- Jarvin does not auto-pull Ollama models.
- Provision the Ollama model yourself on the host machine.
- If you want the embedded path again, set `JARVIN_LLM_BACKEND=llama_cpp`.

## Run The App

Friendly path:

```powershell
python server.py
```

Explicit venv path:

```powershell
.\.venv\Scripts\python server.py
```

## GPU Diagnostics

```powershell
.\.venv\Scripts\python scripts\diagnose_gpu.py
```

What a healthy result should show:

- Torch version ending in `+cu128`
- `cuda_available=True`
- a detected NVIDIA device
- `llama-cpp-python` importing successfully
- `ggml_cuda_init` output listing the GPU

## Useful Test Commands

Full suite:

```powershell
.\.venv\Scripts\python -m pytest
```

Fast targeted checks:

```powershell
.\.venv\Scripts\python -m pytest tests\test_server_launcher.py -q
.\.venv\Scripts\python -m pytest tests\backend\llm\test_runtime_llama_cpp.py tests\backend\util\test_hw_detect.py -q
.\.venv\Scripts\python -m pytest tests\config\test_settings.py tests\memory\test_conversation.py -q
```

## Common Troubleshooting

### Venv Broken After Python Changes

Symptom:

- `.venv\Scripts\python` points at a removed or moved base interpreter

Fix:

```powershell
Remove-Item -Recurse -Force .venv
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-gpu-cu128.txt
.\.venv\Scripts\python -m pip install -e .
```

### Whisper Or Torch Not Using GPU

Run:

```powershell
.\.venv\Scripts\python scripts\diagnose_gpu.py
```

If Torch reports `+cpu`, reinstall from `requirements-gpu-cu128.txt`.

### `llama-cpp-python` Tries To Build From Source

The canonical fix is to install through `requirements-gpu-cu128.txt`, which includes the extra wheel indices for both Torch and the official Windows CUDA wheels for `llama-cpp-python`.

### Microphone Issues

- Check Windows microphone permissions.
- Use the UI or `/audio/devices` route to confirm the selected input device.
- Prefer the included mic scripts for quick hardware checks before changing core audio code.
