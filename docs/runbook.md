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

## Run The Desktop Shell

The new desktop client lives in [clients/jarvin-ui](d:/Projects/Jarvin/clients/jarvin-ui).
It talks to the Python host over HTTP, so start the host first:

```powershell
python server.py
```

Then in a second terminal:

```powershell
cd clients\jarvin-ui
npm install
npm run tauri dev
```

Build sanity check:

```powershell
cd clients\jarvin-ui
npm run tauri build -- --debug --no-bundle
```

Override the host URL if needed:

```powershell
$env:VITE_JARVIN_API_BASE_URL = "http://127.0.0.1:8000"
npm run tauri dev
```

## Run The Shared Mobile / VPN Shell

Build the host-served frontend once:

```powershell
cd clients\jarvin-ui
npm install
npm run build:host
```

Then run the Jarvin host:

```powershell
python server.py
```

Open the shared shell from another device over WireGuard:

```text
http://<wireguard-host-ip>:8000/app/
```

Notes:

- The `/app/` shell reuses the same React client as the Tauri desktop app.
- It uses the same origin as the Jarvin host automatically, so no extra API env var is required for the phone browser path.
- Re-run `npm run build:host` whenever you change the shared frontend.
- Host listener and input-device controls refer to microphones attached to the Jarvin PC, not the phone.
- Remote browser microphone capture is a separate path and usually needs HTTPS or a Tauri mobile shell.

## Build The Tauri Android Shell

The shared React client can also run inside a Tauri Android shell, which is the preferred path for phone voice because it avoids the browser secure-context problems that block remote mic capture on plain HTTP.

Machine paths currently working on this PC:

- Android SDK: `%LOCALAPPDATA%\Android\Sdk`
- Android NDK: `%LOCALAPPDATA%\Android\Sdk\ndk\27.2.12479018`
- Java: `C:\Program Files\Java\jdk-20`

Fast path for a Pixel 8 Pro style device:

```powershell
cd clients\jarvin-ui
npm run tauri:android:pixel:debug
```

That helper will:

- initialize the Android project if it is missing
- ensure the phone-mic permissions are present in the generated Android manifest
- build the shared frontend
- target `aarch64` / `arm64`
- fall back to direct Gradle packaging if Windows blocks the Tauri symlink step

Expected APK output:

```text
clients/jarvin-ui/src-tauri/gen/android/app/build/outputs/apk/arm64/debug/app-arm64-debug.apk
```

Notes:

- The debug APK allows cleartext HTTP so it can reach `http://<wireguard-host-ip>:8000` over WireGuard.
- The mobile client should use the in-app `Host URL` setting to point at the Jarvin machine.
- If you enable Windows Developer Mode later, the plain `npm run tauri:android:build -- --debug --target aarch64` path should become cleaner because Tauri will be allowed to create the symlink it wants during packaging.

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

## Assistant Tool Setup

Jarvin now exposes explicit host-side assistant tools.

Quick checks from chat:

```text
/tool help
/tool weather Seattle
/tool web local llama cpp docs
/tool run git status
```

Google Calendar setup:

1. Create a Google OAuth desktop client in Google Cloud.
2. Save the downloaded JSON file as `secrets/google-calendar-client.json`.
3. Start Jarvin with `python server.py`.
4. From chat, run:

```text
/tool calendar auth
```

That will open a local browser on the host machine for the first authorization and store the token at `data/google-calendar-token.json`.

Optional env overrides:

```powershell
$env:JARVIN_AGENT_WEB_SEARCH_PROVIDER = "duckduckgo_lite"
$env:JARVIN_GOOGLE_SEARCH_API_KEY = ""
$env:JARVIN_GOOGLE_SEARCH_ENGINE_ID = ""
$env:JARVIN_GOOGLE_CALENDAR_CREDENTIALS_FILE = "secrets/google-calendar-client.json"
$env:JARVIN_GOOGLE_CALENDAR_TOKEN_FILE = "data/google-calendar-token.json"
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
