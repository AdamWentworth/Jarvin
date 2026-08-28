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

Jarvin currently has three client surfaces:

- shared React shell served from `/app/`
- Tauri desktop app
- Tauri Android shell

The desktop and mobile clients reuse the same React frontend and talk to the Python host over HTTP.

## Main Runtime Paths

### Typed Chat

1. A client sends `POST /chat`
2. The chat route first tries natural-language tool handling
3. If a tool or planner handles the turn, the tool reply is returned and optionally spoken
4. If a managed calendar, reminder, organizer, or live-weather request remains unhandled, the capability guard reports that no operation occurred
5. Only ordinary conversation falls back to normal LLM chat generation
6. The turn is persisted to SQLite

### Remote Voice

1. A phone client records local microphone audio
2. The client uploads audio to the host transcription path
3. Whisper transcribes on the host
4. Jarvin reviews the transcript confidence before acting on it
5. If the transcript looks shaky, the client shows a confirm/retry card
6. If accepted, the text is sent through normal chat handling
7. Jarvin optionally synthesizes reply audio on the host
8. The client plays that reply through the phone speakers

### Host Listener

Jarvin still supports the host-side always-on listener path:

1. microphone capture
2. VAD / utterance detection
3. Whisper transcription
4. transcript confidence review
5. local clarification prompt when the transcript looks suspicious
6. local LLM reply
7. optional host-side playback

This path is separate from the phone mic flow.

## Core Components

### API App

`backend/api/app.py`

Composes the FastAPI app, mounts routers, serves the shared frontend at `/app/`, and mounts temp audio assets for uploaded audio and synthesized reply playback.

### Chat And Tool Routing

`backend/api/routes/chat.py`
`backend/agent/chat/assistant_chat_tools.py`
`backend/agent/chat/chat_capability_guard.py`

This layer does the assistant orchestration.

It currently handles:

- explicit `/tool ...` commands
- natural-language planner routing
- pending confirmations and approvals for risky host actions
- fail-closed handling when a managed request cannot be translated into a verified operation
- task-scoped host plans with task cards and progress updates
- fallback to normal LLM chat when no tool path applies

### Planner Layer

Jarvin now uses domain-specific planners instead of relying only on brittle regex.

Current planners:

- `backend/agent/weather/weather_request_tools.py`
- `backend/agent/calendar/calendar_request_tools.py`
- `backend/agent/reminders/reminder_request_planner.py`
- `backend/agent/workspace/workspace_request_tools.py`
- `backend/agent/research/research_request_tools.py`
- `backend/agent/briefing/brief_request_planner.py`

The shared follow-up layer:

- `backend/agent/chat/chat_followup_context.py`
- `backend/agent/chat/chat_followup_router.py`

keeps short-lived active-domain context so ambiguous follow-ups like `how about tomorrow?` or `show me more` stay attached to the right tool domain.

### Tool Execution

`backend/agent/host_tool_runtime.py`
`backend/agent/integration_facade.py`
`backend/agent/tasks`

These modules provide deterministic host-side actions such as:

- workspace search
- file reads
- directory listing
- allowlisted commands
- weather lookup
- web research
- built-in calendar operations

### Realtime Updates

`backend/api/routes/live.py`
`backend/listener/live_state.py`

The client uses server-sent events from `/live/stream` as the primary realtime path for listener state, task progress, conversation updates, and action-log changes. Normal chat sends, approvals, uploads, and integration calls remain REST endpoints.

### ASR, LLM, And TTS

- `backend/asr/whisper.py`
- `backend/agent/voice/voice_transcription_review.py`
- `backend/agent/voice/voice_listener_clarification_state.py`
- `backend/llm/runtime_llama_cpp.py`
- `backend/llm/runtime_router.py`
- `backend/llm/runtime_ollama.py`
- `backend/tts/engine.py`

Jarvin prefers local inference and offline voice where possible. Optional external services exist only for integrations like web search.

### Persistence

Conversation and profile state:

- `memory/conversation.py`

Reminder and routine state:

- `memory/reminders.py`

Calendar state:

- `memory/calendar_events.py`

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
- host task planning and approval cards
- voice transcript confidence checks before action
- mobile reminder notifications

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

- built into Jarvin as local SQLite state in the `calendar_events` table
- no external account, OAuth flow, or cloud sync is required
- supports agenda lookup, event CRUD, and simple recurring events
- morning briefs read from the same local calendar store as normal chat/calendar operations

## Important Invariants

- The host is the source of truth for state, tools, and integrations.
- Clients are thin shells and should not own durable assistant state.
- Planner output should stay constrained and feed deterministic tool calls.
- A language-model response must never stand in for a calendar, reminder, weather, or host-tool result.
- Risky actions should remain confirmable and auditable.
- Natural-language flexibility should come from planner layers, not from letting the LLM freestyle raw side effects.

## Key Files

- `server.py`: entrypoint and `.venv` relaunch behavior
- `config.py`: settings, env loading, `.env` support
- `backend/api/app.py`: FastAPI composition and frontend serving
- `backend/api/routes/chat.py`: chat + tool response path
- `backend/agent/chat/assistant_chat_tools.py`: central assistant router
- `backend/agent/host_tool_runtime.py`: workspace-safe host tools
- `backend/agent/integration_facade.py`: external integrations facade
- `backend/agent/tasks`: task-scoped host planning and execution
- `backend/agent/voice`: voice transcript review and listener clarification
- `memory/conversation.py`: conversations and profile
- `memory/calendar_events.py`: local calendar events
- `memory/reminders.py`: reminders and routines
- `clients/jarvin-ui/src/App.tsx`: shared client entrypoint
