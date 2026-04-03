# Jarvin Roadmap

## Current Goal

Build Jarvin into a private, host-run personal AI assistant that supports:

- typed chat
- voice conversation
- agent / task execution workflows
- multiple operating modes
- remote access from personal devices over VPN
- a phone acting as a remote voice client with microphone input and spoken output

## What Exists Today

- local-first FastAPI + Gradio app
- typed chat endpoint and UI path
- embedded local LLM via `llama-cpp-python`
- optional headless Ollama backend with Jarvin-controlled UX
- local GPU-enabled inference on the current Windows machine
- conversation persistence in SQLite
- multi-conversation history and basic user profile context
- Whisper ASR path
- optional TTS path
- basic live status / listener state plumbing
- documentation for architecture, setup, product direction, and model strategy

## Mentioned Goals Not Fully Built Yet

- first-class mode switching in the UI
- remote phone voice access over VPN
- stronger agent / tool execution workflows
- mobile-friendly client experience
- stronger authentication and session handling
- richer memory and project-aware context
- better action logging and auditability
- model selection and tuning from the UI
- asynchronous / more polished response streaming
- better local TTS

## High-Value Features We Have Barely Touched

- explicit tool permission model
- project/workspace contexts
- background jobs and long-running tasks
- exportable conversations and notes
- saved preferences and pinned facts
- settings UI
- model benchmarking harness
- mobile-first interaction design
- remote audio transport design

## Phased Roadmap

### Phase 1: Strong Typed Assistant

Focus on making Jarvin genuinely useful without local audio hardware.

- add first-class mode presets such as `voice_fast`, `chat_balanced`, and `agent_strong`
- improve typed chat UX for desktop and mobile browsers
- expose model/backend selection in a controlled UI
- improve conversation controls: rename, archive, export, pin
- add better progress states such as thinking, running, and speaking

Why this comes first:

- it improves the product immediately on the current setup
- it strengthens the core assistant behavior before more complex voice work
- it supports the future remote-client experience too

### Phase 2: Agent Foundations

Focus on safe, useful action-taking.

- add a tool abstraction layer
- start with safe local tools such as file read, repo search, and command execution
- add permission prompts and clear boundaries for risky actions
- add action logs and auditable traces
- introduce workspace-aware context for coding and project tasks

Why this matters:

- it moves Jarvin closer to the "personal Codex" goal
- it gives typed mode real leverage even before voice is polished

### Phase 3: Memory And Personalization

Focus on making Jarvin feel persistent and helpful over time.

- add short summaries instead of only raw turn history
- store preferences, recurring facts, and pinned context
- support per-project or per-topic working memory
- separate ephemeral context from durable memory

Why this matters:

- better memory improves both chat and agent workflows
- it reduces the need for long prompts on current hardware

### Phase 4: Remote Host Experience

Focus on the "one host, many private clients" shape.

- improve authentication for private remote access
- make the UI genuinely usable from a phone browser over VPN
- support multiple concurrent clients and sessions cleanly
- keep inference and heavy state on the host machine
- improve service boundaries so headless backends are easy to operate

Why this matters:

- this is the deployment shape the project is actually aiming for
- client hardware becomes mostly irrelevant if the host does the work

### Phase 5: Remote Voice Client

Focus on voice again, but through the phone and VPN path rather than local desktop audio devices.

- let a phone send microphone audio to Jarvin over the private network
- let Jarvin return text plus playable spoken audio to the phone
- make voice round-trips low-latency enough to feel conversational
- support interruption, stop-talking, and resume behavior
- decide whether transport should stay request/response first or evolve toward streaming audio

Why this is exciting:

- it unblocks voice usage even when the host machine has no attached mic or speakers
- it matches the real-world way the system will likely be used

### Phase 6: Voice Polish And Higher-End Models

Focus on improving quality after the product shape is solid.

- benchmark stronger models as host hardware improves
- evaluate better TTS engines
- improve ASR latency/accuracy tradeoffs by mode
- add richer voice settings and personas

Why this comes later:

- the product gets more value first from better modes, tools, and hosting shape
- better hardware will make later model decisions more meaningful

## Best Next Steps

If choosing the next implementation slice today, prefer:

1. mode presets and typed/mobile UX
2. tool abstraction and safe agent actions
3. remote-host authentication and session model
4. remote phone voice path over VPN

## Decision Rule

When prioritizing between features, prefer the work that improves all future modes at once:

- backend abstraction beats one more hardcoded model
- mobile-friendly chat UX beats local desktop-only polish
- safe tooling beats raw prompt tweaks
- host/client architecture beats assumptions that all hardware is local
