# Jarvin Agent Guide

Start here before making changes in this repo.

## Working Assumptions

- Jarvin is Windows-first today.
- The canonical environment is the repo-local `.venv`.
- `python server.py` is the friendly command, but the repo still expects packages to be installed into `.venv`.
- Normal operation should remain local-first and offline-first.
- User data in `data/` is real local state; treat schema and persistence changes carefully.

## Mental Model

The core product loop is:

1. background listener captures an utterance
2. VAD decides utterance boundaries
3. Whisper transcribes audio
4. local llama.cpp runtime generates a reply
5. the reply is persisted and optionally synthesized to speech
6. live state is pushed to the UI / API

If a change affects one part of that loop, trace both the upstream input and downstream state update before editing.

## Files That Matter Most

- [`server.py`](../server.py): process bootstrap and venv re-exec
- [`config.py`](../config.py): most runtime knobs
- [`backend/api/app.py`](../backend/api/app.py): startup, routers, lifespan
- [`backend/listener/runner.py`](../backend/listener/runner.py): main background loop
- [`backend/core/pipeline.py`](../backend/core/pipeline.py): utterance processing and persistence boundary
- [`backend/asr/whisper.py`](../backend/asr/whisper.py): Whisper runtime/device behavior
- [`backend/llm/runtime_llama_cpp.py`](../backend/llm/runtime_llama_cpp.py): local LLM loading and GPU behavior
- [`memory/conversation.py`](../memory/conversation.py): SQLite state, migrations, active conversation model
- [`ui/app.py`](../ui/app.py): Gradio composition and polling

## Repo-Specific Invariants

- `process_utterance()` already appends conversation turns. Do not duplicate that in the listener.
- `set_status()` should not create a new UI turn event. Only `set_snapshot()` advances the sequence.
- GPU setup is currently encoded in `requirements-gpu-cu128.txt` plus `scripts/diagnose_gpu.py`.
- Keep generated assets and local runtime state out of commits: `.venv/`, `models/`, `temp/`, `data/`, caches, and compiled artifacts.

## When In Doubt

- Read `docs/architecture.md` first.
- Use `docs/runbook.md` for commands instead of guessing.
- Read `docs/product-vision.md` and `docs/local-model-strategy.md` before making broad UX, model, or latency decisions.
- Use `.agents/change-checklist.md` to decide what to verify before closing work.
