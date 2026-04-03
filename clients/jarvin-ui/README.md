# Jarvin Desktop Shell

This is the new Tauri + React desktop client for Jarvin.

It is intentionally built as an HTTP-first shell over the Python host so the same frontend architecture can later be reused for Tauri mobile.

## Current Scope

- desktop-only testing for now
- typed chat workspace
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

## Build Check

```powershell
cd clients\jarvin-ui
npm run tauri build -- --debug --no-bundle
```

## Host URL

By default the desktop shell talks to:

```text
http://127.0.0.1:8000
```

To point it somewhere else:

```powershell
$env:VITE_JARVIN_API_BASE_URL = "http://your-host:8000"
npm run tauri dev
```
