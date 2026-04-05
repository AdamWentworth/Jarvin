# Jarvin Roadmap

## Current Direction

Jarvin is a private, host-run personal AI assistant.

The intended shape is:

- one Windows host machine running the backend, models, GPU inference, and durable state
- desktop and phone clients connecting to that host over local network or WireGuard
- voice, tools, memory, and integrations layered on top of a local-first core

The goal is not to train a brand-new foundation model. The goal is to build a strong assistant system around good local models, reliable tool use, useful memory, and polished clients.

## What Exists Today

- FastAPI host serving the shared `/app/` shell and APIs
- shared React frontend served at `/app/`
- Tauri desktop client
- Tauri Android shell for phone testing
- typed chat with multi-conversation history
- mobile/VPN voice path:
  - phone microphone upload
  - host-side transcription
  - spoken reply playback on the phone
- local `llama.cpp` runtime with optional Ollama backend support
- SQLite-backed profile and conversation persistence
- reminder and routine storage with CRUD APIs
- morning briefs that combine weather, calendar, and reminders
- weather lookup with visual weather cards in the client
- Google Calendar integration with event CRUD
- web research via DuckDuckGo-backed search, page fetch, and summarization
- safe host-side tools for:
  - repo search
  - file reads
  - directory listing
  - limited command execution
- natural-language planners for:
  - weather
  - calendar
  - reminders
  - workspace actions
  - research
  - briefs
- shared follow-up routing so ambiguous short replies stay in the right domain

## What Is Still Missing Or Thin

- real authentication and session guardrails for remote clients
- explicit permission / approval flows for risky host actions
- proactive notifications on the phone
- stronger long-term memory and preference storage
- background jobs and watch-style agents
- richer integrations such as email, messaging, and home/device control
- better action tracing, auditability, and operator logs
- more polished streaming and interruption behavior
- stronger TTS quality and voice options

## Phase Status

### Phase 1: Core Local Assistant

Status: largely done

- local LLM runtime
- typed chat
- conversation persistence
- basic profile context
- reminders, routines, and briefs

### Phase 2: Tooling And Planner Layer

Status: in progress, but already useful

- safe host-side tool layer exists
- natural-language planners now cover core domains
- follow-up routing has started to reduce brittle phrasing

Still needed:

- confirmation model for risky actions beyond calendar edits
- better traces and permission UX
- more robust multi-step task execution

### Phase 3: Remote Clients And Mobile Voice

Status: in progress, working for real use

- shared React client
- Tauri desktop shell
- host-served `/app/` shell
- Tauri Android shell
- remote mic upload and phone speaker playback

Still needed:

- richer mobile notifications
- smoother reconnect and session UX
- more polished interruption and streaming audio behavior

### Phase 4: Reliability, Guardrails, And Operations

Status: next major focus

- remote auth
- better diagnostics and action logs
- safer tool approval model
- clearer host health and background task monitoring

### Phase 5: Proactive Assistant Behavior

Status: next major product leap

- scheduled morning brief delivery
- due reminder notifications
- host health alerts
- assistant-initiated nudges instead of request-only behavior

### Phase 6: Memory And Personalization

Status: early groundwork only

- durable preferences
- pinned facts
- project-aware memory
- better summaries instead of raw turn reliance
- user-specific style and routine adaptation

### Phase 7: Richer Integrations And Background Agents

Status: later

- email
- messaging
- downloads and system tasks
- background research or repo-watch agents
- device / smart-home style integrations

### Phase 8: Quality Upgrades

Status: later

- stronger models as hardware improves
- better TTS engines
- better streaming and interruption
- smarter per-mode routing and benchmarking

## Best Next Slices

If we are choosing what to build next, the highest-value slices are:

1. phone notifications for reminders and briefs
2. explicit permission / confirmation flow for risky host actions
3. lightweight auth for remote clients
4. richer long-term memory and saved preferences
5. background jobs and watch-style tasks

## Decision Rule

When choosing between features, prefer the work that makes Jarvin feel more like an actual assistant instead of a collection of commands.

That usually means:

- planner + tool improvements over more regex
- client reliability over one-off UI polish
- proactive delivery over another passive endpoint
- safe orchestration over raw power
- host/client architecture over device-specific hacks
