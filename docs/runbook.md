# Jarvin Runbook

## Environment

- Run commands from the repo root.
- Use Python 3.11 for the project virtual environment.
- Jarvin loads `.env` automatically from the repo root.
- Environment variables use the `JARVIN_` prefix.

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

## Core Host Startup

Run Jarvin from the repo root:

```powershell
python server.py
```

The default host bind is:

```text
http://0.0.0.0:8000
```

Useful local entry points:

- `http://127.0.0.1:8000/ui` for the legacy Gradio UI
- `http://127.0.0.1:8000/app/` for the shared React shell

## Useful `.env` Settings

Minimal common settings:

```dotenv
JARVIN_LLM_BACKEND=llama_cpp
JARVIN_AGENT_WEB_SEARCH_PROVIDER=duckduckgo_lite
JARVIN_DEFAULT_WEATHER_LOCATION=Seattle
```

Useful integration paths:

```dotenv
JARVIN_GOOGLE_CALENDAR_CREDENTIALS_FILE=secrets/google-calendar-client.json
JARVIN_GOOGLE_CALENDAR_TOKEN_FILE=data/google-calendar-token.json
```

## Run The Desktop Shell

Start the host first:

```powershell
python server.py
```

Then in another terminal:

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

Override the API base URL if needed:

```powershell
$env:VITE_JARVIN_API_BASE_URL = "http://127.0.0.1:8000"
npm run tauri dev
```

## Run The Shared `/app/` Shell

Build the host-served frontend:

```powershell
cd clients\jarvin-ui
npm install
npm run build:host
```

Then run the Jarvin host:

```powershell
python server.py
```

Open it from another device:

```text
http://<host-or-wireguard-ip>:8000/app/
```

Notes:

- The `/app/` shell reuses the same React frontend as the Tauri desktop app.
- It talks to the same origin automatically, so no extra API env var is needed for the browser path.
- Remote browser microphone capture is limited by browser secure-context rules. Plain HTTP over WireGuard is fine for typed chat, but phone mic access is better through the Tauri mobile shell.

## Build The Tauri Android Shell

From the client directory:

```powershell
cd clients\jarvin-ui
npm run tauri:android:pixel:debug
```

This helper will:

- initialize the Android project if needed
- build the shared frontend
- target `arm64`
- fall back to direct Gradle packaging on Windows when Tauri hits the symlink issue

Primary artifact path:

```text
clients/jarvin-ui/artifacts/jarvin-mobile-arm64-debug.apk
```

Generated Gradle output path:

```text
clients/jarvin-ui/src-tauri/gen/android/app/build/outputs/apk/arm64/debug/app-arm64-debug.apk
```

## Install The Android APK

If the phone is connected over USB with developer mode and USB debugging enabled:

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" install -r "D:\Projects\Jarvin\clients\jarvin-ui\artifacts\jarvin-mobile-arm64-debug.apk"
```

## Mobile Host Connection

When the Android app opens:

1. Open `Settings`
2. Set `Host URL` to your Jarvin host, for example:

```text
http://10.x.x.x:8000
```

3. Save and reconnect

The mobile shell should use the phone microphone and speakers, while host listener controls still refer to audio devices on the Jarvin PC.

## Search Integration

Jarvin currently uses DuckDuckGo Lite as the default search provider.

Validate search:

```powershell
.\.venv\Scripts\python scripts\validate_integrations.py --search-only --query "llama.cpp windows cuda docs"
```

Expected result:

- `status=ok`
- `provider=duckduckgo_lite`
- non-zero `results`

## Google Calendar Setup

1. Create a Google OAuth desktop client in Google Cloud.
2. Save the JSON file as:

```text
secrets/google-calendar-client.json
```

3. Start Jarvin:

```powershell
python server.py
```

4. In chat, say one of:

```text
connect my Google Calendar
authorize my Google Calendar
```

5. Complete the browser OAuth flow on the host machine.

The saved token lands at:

```text
data/google-calendar-token.json
```

Validate calendar setup:

```powershell
.\.venv\Scripts\python scripts\validate_integrations.py --calendar-only
```

## Things To Try In Chat

Weather:

```text
What's the weather in Burnaby near Metrotown?
How about tomorrow?
```

Calendar:

```text
What's on my calendar today?
Put lunch with Sam on my calendar tomorrow at noon.
Move lunch with Sam back an hour.
Delete lunch with Sam from my calendar.
```

Reminders and briefs:

```text
Remind me to call mom tomorrow at 5pm.
Every weekday at 8am remind me to stretch.
Give me my morning brief.
```

Workspace and research:

```text
Could you look through the codebase for include_router?
Pull up backend/api/app.py lines 10 to 30.
Research llama.cpp windows cuda docs for me.
What else did you find?
```

## Useful Test Commands

Full backend suite:

```powershell
.\.venv\Scripts\python -m pytest tests\backend -q
```

Targeted integration checks:

```powershell
.\.venv\Scripts\python scripts\validate_integrations.py --search-only
.\.venv\Scripts\python scripts\validate_integrations.py --calendar-only
```

GPU diagnostics:

```powershell
.\.venv\Scripts\python scripts\diagnose_gpu.py
```

## Common Troubleshooting

### Venv Broken After Python Changes

```powershell
Remove-Item -Recurse -Force .venv
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-gpu-cu128.txt
.\.venv\Scripts\python -m pip install -e .
```

### Android App Connects But Voice Fails

Check:

- the phone `Host URL`
- that the host is running
- that the phone can reach `http://<host-ip>:8000/healthz`
- that the app build is current if client-side voice code changed

### Calendar Exists But Is Not Authorized

The validator will show:

- credentials present
- token missing

In that case, re-run the auth flow from chat.

### Search Provider Confusion

If search should stay on DuckDuckGo Lite, keep:

```dotenv
JARVIN_AGENT_WEB_SEARCH_PROVIDER=duckduckgo_lite
```

### Host-Only Vs Client-Only Audio

- Host listener controls operate on microphones attached to the Jarvin PC
- Remote phone voice uses the phone microphone and speakers through the mobile client
