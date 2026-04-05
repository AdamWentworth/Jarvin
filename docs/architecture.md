# Jarvin Architecture

## Purpose

Jarvin is a private, host-run personal assistant.

The host machine owns:

- model runtimes
- GPU inference
- SQLite persistence
- tool execution
- calendar and reminder state
- voice processing

Other devices act as clients over local network or WireGuard.

## System Shape

### Host

The host is a FastAPI service started from `python server.py`.

It is responsible for:

- app startup and background listener lifecycle
- ASR, LLM, and TTS orchestration
- chat, reminder, workspace, and integration APIs
- serving UI surfaces
- persisting conversations and reminders

### Clients

Jarvin currently has four client surfaces:

- shared React shell served from `/app/`
- Tauri desktop app
- Tauri Android shell

The desktop and mobile clients reuse the same React frontend and talk to the Python host over HTTP.

## Main Runtime Paths

### Typed Chat

1. A client sends `POST /chat`
2. The chat route first tries natural-language tool handling
3. If a tool or planner handles the turn, the tool reply is returned and optionally spoken
4. Otherwise Jarvin falls back to normal LLM chat generation
5. The turn is persisted to SQLite

### Remote Voice

1. A phone client records local microphone audio
2. The client uploads audio to the host transcription path
3. Whisper transcribes on the host
4. The transcribed text is sent through normal chat handling
5. Jarvin optionally synthesizes reply audio on the host
6. The client plays that reply through the phone speakers

### Host Listener

Jarvin still supports the host-side always-on listener path:

1. microphone capture
2. VAD / utterance detection
3. Whisper transcription
4. local LLM reply
5. optional host-side playback

This path is separate from the phone mic flow.

## Core Components

### API App

`backend/api/app.py`

Composes the FastAPI app, mounts routers, serves the shared frontend at `/app/`, and mounts temp audio assets for uploaded audio and synthesized reply playback.

### Chat And Tool Routing

`backend/api/routes/chat.py`
`backend/agent/chat_tools.py`

This layer does the assistant orchestration.

It currently handles:

- explicit `/tool ...` commands
- natural-language planner routing
- pending confirmations for risky calendar changes
- fallback to normal LLM chat when no tool path applies

### Planner Layer

Jarvin now uses domain-specific planners instead of relying only on brittle regex.

Current planners:

- `backend/agent/weather_tools.py`
- `backend/agent/calendar_tools.py`
- `backend/agent/reminder_planner.py`
- `backend/agent/workspace_tools.py`
- `backend/agent/research_tools.py`
- `backend/agent/brief_planner.py`

The shared follow-up layer:

- `backend/agent/followup_context.py`
- `backend/agent/followup_router.py`

keeps short-lived active-domain context so ambiguous follow-ups like `how about tomorrow?` or `show me more` stay attached to the right tool domain.

### Tool Execution

`backend/agent/tools.py`
`backend/agent/external_tools.py`

These modules provide deterministic host-side actions such as:

- workspace search
- file reads
- directory listing
- allowlisted commands
- weather lookup
- web research
- Google Calendar operations

### ASR, LLM, And TTS

- `backend/asr/whisper.py`
- `backend/llm/runtime_llama_cpp.py`
- `backend/llm/runtime_router.py`
- `backend/llm/runtime_ollama.py`
- `backend/tts/engine.py`

Jarvin prefers local inference and offline voice where possible. Optional external services exist only for integrations like web search or Google Calendar.

### Persistence

Conversation and profile state:

- `memory/conversation.py`

Reminder and routine state:

- `memory/reminders.py`

The default database location is:

- `data/jarvin.sqlite3`

### Client Frontend

Shared React frontend:

- `clients/jarvin-ui/src`

Desktop shell:

- `clients/jarvin-ui/src-tauri`

The shared client is also built for host serving under `/app/`, which gives a browser-accessible shell over WireGuard without needing a separate web app codebase.

## Major Product Capabilities

### Assistant Domains

Jarvin currently has meaningful support for:

- weather
- calendar lookup and event CRUD
- reminders and routines
- morning / daily briefs
- workspace and repo operations
- web research

### Response Enrichment

Tool replies can carry structured payloads back through the chat API.

Example:

- weather replies include visual card data such as icon, temperature, rain chance, wind, and location

This allows the client to render richer responses than plain text alone.

## Integrations

### Search

Default provider:

- DuckDuckGo Lite

Jarvin can search, fetch top pages, and summarize what it found.

### Weather

- Open-Meteo

### Calendar

- Google Calendar via OAuth desktop credentials and a saved token on the host

## Important Invariants

- The host is the source of truth for state, tools, and integrations.
- Clients are thin shells and should not own durable assistant state.
- Planner output should stay constrained and feed deterministic tool calls.
- Risky actions should remain confirmable and auditable.
- Natural-language flexibility should come from planner layers, not from letting the LLM freestyle raw side effects.

## Key Files

- `server.py`: entrypoint and `.venv` relaunch behavior
- `config.py`: settings, env loading, `.env` support
- `backend/api/app.py`: FastAPI composition and frontend serving
- `backend/api/routes/chat.py`: chat + tool response path
- `backend/agent/chat_tools.py`: central assistant router
- `backend/agent/external_tools.py`: external integrations and helper tools
- `backend/agent/tools.py`: workspace-safe host tools
- `memory/conversation.py`: conversations and profile
- `memory/reminders.py`: reminders and routines
- `clients/jarvin-ui/src/App.tsx`: shared client entrypoint
