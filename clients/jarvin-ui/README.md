# Jarvin Client

This is the shared React frontend for Jarvin.

It currently powers:

- the Tauri desktop app
- the host-served `/app/` shell
- the Tauri Android shell

The Python host remains the source of truth for models, GPU inference, persistence, and tool execution.

## What The Client Does Today

- typed chat with multi-conversation history
- remote microphone capture
- spoken reply playback on the phone
- model/backend selection
- listener and device controls
- profile and diagnostics surfaces
- weather cards and other richer tool responses

## Run The Desktop Client

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

## Build The Host-Served Shell

To serve the same UI from the Python host at `/app/`:

```powershell
cd clients\jarvin-ui
npm run build:host
```

Then open:

```text
http://your-host-or-wireguard-ip:8000/app/
```

## Capture Demo Media

The demo capture uses mocked host responses, so it does not start a local model, use the microphone, mutate reminders, or touch real workspace files.

```powershell
cd clients\jarvin-ui
npm run capture:demo
```

Output is written to:

```text
clients/jarvin-ui/artifacts/demo-media/jarvin
```

## Build Checks

```powershell
cd clients\jarvin-ui
npm run build
npm run build:host
npm run tauri build -- --debug --no-bundle
```

## Host URL Behavior

Desktop default:

```text
http://127.0.0.1:8000
```

Override it for the desktop shell:

```powershell
$env:VITE_JARVIN_API_BASE_URL = "http://your-host:8000"
npm run tauri dev
```

The host-served `/app/` shell uses the same origin automatically.

## Android / Tauri Mobile

Available commands:

```powershell
cd clients\jarvin-ui
npm run tauri:android:init
npm run tauri:android:dev
npm run tauri:android:build
npm run tauri:android:pixel:debug
```

The helper build is the most reliable path on this machine:

```powershell
cd clients\jarvin-ui
npm run tauri:android:pixel:debug
```

It will:

- ensure the Android project exists
- build the shared frontend
- target `aarch64` / `arm64`
- fall back to direct Gradle packaging when Windows Developer Mode is off

Primary APK artifact:

```text
clients/jarvin-ui/artifacts/jarvin-mobile-arm64-debug.apk
```

Generated Gradle output:

```text
clients/jarvin-ui/src-tauri/gen/android/app/build/outputs/apk/arm64/debug/app-arm64-debug.apk
```

## Android App Flow

1. Install the APK on the phone
2. Connect the phone to WireGuard if you are remote
3. Open the Jarvin app
4. Set `Host URL` in Settings
5. Use typed chat or the mobile mic button

## Voice Notes

- Host listener controls refer to microphones attached to the Jarvin PC
- Remote microphone capture is a separate client-side path
- The Tauri Android shell is the preferred phone voice path because it avoids browser secure-context limitations on plain HTTP
