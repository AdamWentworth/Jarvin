# Jarvin Client

This is the shared React frontend for Jarvin.

It currently powers the Tauri desktop client, and it is intentionally built as an HTTP-first shell over the Python host so the same frontend architecture can be reused for Tauri mobile and a VPN-accessed phone browser shell.

## Current Scope

- desktop-only testing for now
- typed chat workspace
- first-pass remote client microphone capture
- conversation switching and management
- model/backend settings
- device and listener controls
- profile editing
- diagnostics view

The host machine still runs the actual Jarvin backend, models, and GPU workload.

## Run It

From the repo root, start the host first:

```powershell
python server.py
```

Then in a second terminal:

```powershell
cd clients\jarvin-ui
npm install
npm run tauri dev
```

## Build The Host-Served Mobile Shell

To serve the same UI from the Python host at `/app/` for phone or VPN testing:

```powershell
cd clients\jarvin-ui
npm run build:host
```

Then open:

```text
http://your-host-or-wireguard-ip:8000/app/
```

## Build Check

```powershell
cd clients\jarvin-ui
npm run tauri build -- --debug --no-bundle
npm run build:host
```

## Host URL

By default the desktop shell talks to:

```text
http://127.0.0.1:8000
```

The host-served `/app/` shell uses the same origin automatically, so it works cleanly over a WireGuard IP without extra env vars.

Voice note:

- Host listener and input-device controls refer to microphones attached to the Jarvin host machine.
- Remote microphone capture is a separate client-side path and typically requires HTTPS or a Tauri mobile shell.

To point the desktop shell somewhere else:

```powershell
$env:VITE_JARVIN_API_BASE_URL = "http://your-host:8000"
npm run tauri dev
```

## Android / Tauri Mobile

The same frontend is now prepared for a Tauri Android shell, and this machine can now generate an `arm64` debug APK for a Pixel 8 Pro style device.

Available commands:

```powershell
cd clients\jarvin-ui
npm run tauri:android:init
npm run tauri:android:dev
npm run tauri:android:build
npm run tauri:android:pixel:debug
```

Before those commands can work, the machine needs:

- Android Studio or the Android command-line SDK tools
- Android SDK + NDK
- `ANDROID_HOME`
- `ANDROID_SDK_ROOT`
- `NDK_HOME`
- `JAVA_HOME`

This repo now includes [tauri.android.conf.json](d:/Projects/Jarvin/clients/jarvin-ui/src-tauri/tauri.android.conf.json) so Android can use a mobile-specific app name and identifier while still reusing the same frontend.

Important:

- The mobile client should usually point at your Jarvin host over WireGuard using the in-app host URL setting.
- Remote microphone capture should use the phone microphone, not the host PC, once the app is running in the Tauri mobile shell.
- The helper script adds the required Android audio permissions for the generated mobile project before building.

### Pixel 8 Pro Debug Build

Use the helper when you want a repeatable `arm64` debug APK without remembering the full workaround sequence:

```powershell
cd clients\jarvin-ui
npm run tauri:android:pixel:debug
```

It will:

- ensure the Android project exists
- ensure the `aarch64-linux-android` Rust target exists
- build the shared frontend
- try the normal Tauri Android build first
- fall back to direct Gradle packaging on Windows if Developer Mode is off and the symlink step is blocked

The generated APK lands at:

```text
clients/jarvin-ui/src-tauri/gen/android/app/build/outputs/apk/arm64/debug/app-arm64-debug.apk
```

When the app opens on the phone:

1. Connect the phone to WireGuard.
2. Open `Settings` in the Jarvin mobile shell.
3. Set `Host URL` to your Jarvin host, for example `http://10.x.x.x:8000`.
4. Save the host and reconnect.

Note:

- The debug build allows cleartext HTTP so you can talk to the host over WireGuard without setting up HTTPS first.
- A normal `npm run tauri:android:build` still hits a Windows symlink permission issue on this machine when Developer Mode is off, so the helper script handles that fallback automatically.
