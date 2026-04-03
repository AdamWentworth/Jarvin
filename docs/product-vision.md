# Jarvin Product Vision

## What Jarvin Is

Jarvin is meant to become a local-first personal AI assistant that can be used in more than one mode:

- voice conversation
- typed chat
- agent / task-execution mode
- mixed mode where replies can be shown as text, spoken aloud, or both

The long-term goal is closer to "my own Codex that can speak" than to "a single chatbot with a microphone attached."

## Product Principles

- Local-first by default: regular inference should stay on-device.
- Mode-aware, not one-size-fits-all: fast voice turns and deep agent work have different latency and model needs.
- Safe execution boundaries: agent abilities should be explicit and toggleable, not always-on.
- Text remains first-class: every voice interaction should still have a text representation for review, editing, and debugging.
- Spoken output is optional: TTS should be a presentation layer, not a requirement for every reply.

## Target Interaction Modes

### Voice Fast

Use when the user wants natural back-and-forth speech.

Success looks like:

- low latency after the user stops speaking
- short spoken answers by default
- graceful interruption and restart behavior
- minimal tool use unless explicitly requested

### Chat Balanced

Use when the user is typing or when voice latency matters less.

Success looks like:

- better reasoning than the fastest voice mode
- richer context from recent conversation and user profile
- text-first UX with optional TTS playback

### Agent Strong

Use when the user wants Jarvin to plan, edit files, run commands, browse, or complete tasks.

Success looks like:

- stronger reasoning and instruction following
- longer responses when needed
- explicit tool gating, logs, and confirmation points
- less emphasis on immediate spoken latency

## Design Consequences

- The repo should support multiple LLM backends and multiple local models.
- Model choice should be configurable per mode instead of being treated as a single global default forever.
- ASR, LLM, and TTS settings should be profile-driven so the app can trade quality for latency deliberately.
- The UI should eventually expose mode toggles instead of hiding everything behind one pipeline.

## Near-Term Decision Rule

On current hardware, do not optimize for a single "best overall" model. Optimize for:

1. a fast small-model path that makes voice mode feel responsive
2. a somewhat stronger local model path for typing and light agent work
3. a backend abstraction that will let the repo adopt larger models later without rewriting the whole app
