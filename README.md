# Jarvin

Jarvin is a private, host-run personal AI assistant.

It is designed around one trusted machine doing the real work:

- local LLM inference
- voice processing
- persistence
- tool execution
- integrations

Desktop and phone clients then connect to that host over local network or WireGuard.

## Current Capabilities

- local `llama.cpp` runtime with optional headless Ollama backend
- typed chat with multi-conversation history
- legacy Gradio UI at `/ui`
- shared React client served at `/app/`
- Tauri desktop app
- Tauri Android shell
- remote phone voice:
  - phone microphone capture
  - host-side transcription
  - phone speaker playback of Jarvin replies
- SQLite-backed profile and conversation memory
- reminders and routines
- morning briefs that combine weather, calendar, and reminders
- Google Calendar integration with event CRUD
- DuckDuckGo-backed web research with page fetch and summarization
- safe host-side assistant tools for workspace and repo tasks
- natural-language planners for:
  - weather
  - calendar
  - reminders
  - workspace actions
  - research
  - daily briefs

## Product Shape

Jarvin is not trying to become a custom foundation model.

The project is focused on building a strong assistant system around local models:

- voice input and output
- memory
- tools
- integrations
- clients
- planning and follow-up handling
- proactive assistant behavior over time

## Quick Start

Create the virtual environment:

```powershell
py -3.11 -m venv .venv
```

Install dependencies:

```powershell
.\.venv\Scripts\python -m pip install -r requirements-gpu-cu128.txt
.\.venv\Scripts\python -m pip install -e .
```

Run the host:

```powershell
python server.py
```

Then open one of:

- `http://127.0.0.1:8000/ui`
- `http://127.0.0.1:8000/app/`

## Clients

### Tauri Desktop

```powershell
cd clients\jarvin-ui
npm install
npm run tauri dev
```

### Host-Served Shared Shell

```powershell
cd clients\jarvin-ui
npm run build:host
python server.py
```

Then open:

```text
http://<host-or-wireguard-ip>:8000/app/
```

### Tauri Android

```powershell
cd clients\jarvin-ui
npm run tauri:android:pixel:debug
```

Primary APK artifact:

```text
clients/jarvin-ui/artifacts/jarvin-mobile-arm64-debug.apk
```

## Example Prompts

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

## Integrations

### Search

Default search provider:

- DuckDuckGo Lite

Validate search:

```powershell
.\.venv\Scripts\python scripts\validate_integrations.py --search-only --query "llama.cpp windows cuda docs"
```

### Google Calendar

Save your OAuth desktop client JSON at:

```text
secrets/google-calendar-client.json
```

Then ask Jarvin:

```text
connect my Google Calendar
```

Validate calendar setup:

```powershell
.\.venv\Scripts\python scripts\validate_integrations.py --calendar-only
```

## Repo Guide

Important paths:

- `server.py`: host entrypoint
- `config.py`: settings and `.env` loading
- `backend/api/app.py`: FastAPI app assembly
- `backend/api/routes/chat.py`: chat endpoint
- `backend/agent/chat_tools.py`: planner and tool router
- `memory/conversation.py`: conversations and profile
- `memory/reminders.py`: reminders and routines
- `clients/jarvin-ui`: shared desktop/mobile client
- `docs/runbook.md`: operational instructions
- `docs/architecture.md`: current system shape
- `docs/roadmap.md`: product direction and next phases

## Testing

Backend suite:

```powershell
.\.venv\Scripts\python -m pytest tests\backend -q
```

Integration validation:

```powershell
.\.venv\Scripts\python scripts\validate_integrations.py --search-only
.\.venv\Scripts\python scripts\validate_integrations.py --calendar-only
```

GPU diagnostics:

```powershell
.\.venv\Scripts\python scripts\diagnose_gpu.py
```

## Detailed Docs

- [Runbook](docs/runbook.md)
- [Architecture](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [Client README](clients/jarvin-ui/README.md)
