# Local Model Strategy

## Current Hardware Assumption

This strategy is written for the current local setup:

- Windows
- NVIDIA GTX 1070 with 8 GB VRAM
- about 64 GB system RAM
- `llama-cpp-python==0.3.4`
- Whisper on CUDA when available

## Deployment Implication

Because the long-term plan is to run Jarvin on one main machine and access it remotely from other devices over VPN, model selection should be optimized for the host machine only.

That means:

- phone or tablet hardware is mostly irrelevant if they are just clients
- the host runtime should eventually be easy to expose behind a private local API
- operational simplicity matters, not just raw tokens per second

## Embedded Vs Headless Service

On current hardware, embedded `llama.cpp` is still the best default for simplicity and direct control.

An Ollama-style headless service becomes interesting when:

- Jarvin is serving multiple devices
- you want a stable HTTP boundary between UI clients and inference
- you want Jarvin to keep full UX control while the host runs model inference in a separate process

The key point is that Ollama should be treated as an optional engine, not as the product surface.
Jarvin should remain the only user-facing UI and orchestration layer.

## What This Hardware Is Good At

This machine can run small and medium quantized local models comfortably enough for a proof of concept, but it is not a good fit for:

- 20B-class local models as a default interactive path
- newer GGUF families that require a newer llama.cpp stack than the repo currently uses
- one giant model doing fast voice chat, tool use, and deep reasoning all at once

## Current Best-Fit Model Shape

For this box, the best user experience will usually come from:

- 3B-ish models for fast voice and chat
- an optional 7B model for slower but stronger text or light agent work
- keeping the heavyweight reasoning models as future work until hardware and backend support improve

## Practical Recommendations

### Best Default For Fast Interaction

`qwen2.5-3b-instruct` is the best current bet for the repo's "feels responsive" path.

Why:

- it is small enough to fit the machine well
- it loaded successfully on the current CUDA-backed runtime
- it was one of the fastest models in a quick local smoke benchmark
- it is a better fit than forcing a 7B model into every turn

Recommended env override:

```powershell
$env:JARVIN_LLM_FORCE_LOGICAL_NAME = "qwen2.5-3b-instruct"
```

### Stronger But Slower Option

`mistral-7b-instruct` remains a good "think a little harder" option when the user is typing or when latency matters less.

Why:

- it already works in the repo today
- it is meaningfully stronger than the tiny fallback class
- it is still feasible on the current machine, just slower

Recommended env override:

```powershell
$env:JARVIN_LLM_FORCE_LOGICAL_NAME = "mistral-7b-instruct"
```

### Fast Fallback

`phi-3-mini-4k-instruct` is still useful as a safe fallback for constrained or brittle environments, but it should not be the only target forever.

Why:

- it is small and stable
- it loads quickly
- it gives the repo a low-risk baseline

### Interesting But Not Yet Primary

`llama-3.2-3b-instruct` is now recognized by the repo and is worth testing, but it should be validated in real conversations before becoming a default.

Why:

- it fits the machine well
- it loaded successfully in a local smoke test
- template handling matters a lot for quality, so real chat behavior is more important than a synthetic benchmark

### Defer For Now

These are not the right near-term targets on the current stack:

- `DeepSeek-R1-Distill-Qwen-7B`
- `Qwen3` GGUF variants
- `Ministral 3` GGUF variants
- OpenAI `gpt-oss-20b`

Reasons:

- some failed to load on the current `llama-cpp-python` version
- some are a poor fit for 8 GB VRAM in an interactive voice product
- `gpt-oss` deserves a different backend strategy when hardware improves

## Quick Local Benchmark Notes

A lightweight local smoke run on this machine gave this rough shape:

- `qwen2.5-3b-instruct`: about 48 tokens/sec
- `llama-3.2-3b-instruct`: about 49 tokens/sec in a plain completion smoke test
- `phi-3-mini-4k-instruct`: about 42 tokens/sec
- `mistral-7b-instruct`: about 29 tokens/sec
- `DeepSeek-R1-Distill-Qwen-7B`: failed to load on the current stack

Treat these as directional, not as a formal benchmark. The main point is that the 3B class feels much better for interactive use on this hardware than the 7B class.

## Code Optimizations That Matter Most

### 1. Add Mode-Based Presets

The repo should stop treating "voice chat" and "agent work" as the same runtime profile.

Near-term target:

- `voice_fast`: smaller model, short replies, lower `max_tokens`, optional TTS
- `chat_balanced`: slightly richer context and longer replies
- `agent_strong`: longer outputs, stronger model, explicit tool mode

### 2. Keep Chat Template Handling Correct

Wrong chat formatting quietly hurts response quality more than many people expect.

Near-term target:

- map each local model family to the right chat template
- avoid benchmarking models with the wrong prompt format and then concluding the model is bad

### 3. Keep The ASR Hot Path In Memory

The listener path now transcribes in-memory PCM directly instead of depending on a temporary WAV round-trip.

Next target:

- keep file writes optional for debugging or playback instead of mandatory
- measure whether disabling utterance WAV capture by default improves perceived latency further

Why it matters:

- less per-turn I/O
- lower latency
- simpler hot path

### 4. Move TTS Off The Critical Path

Right now reply synthesis is part of the same serial turn pipeline.

Near-term target:

- publish the text reply first
- synthesize speech in the background
- let the UI play audio when ready

Why it matters:

- typed users get faster perceived responses
- spoken-output users still get audio, just without delaying the whole turn

### 5. Tune Whisper For Responsiveness

Whisper accuracy is important, but voice UX breaks first on latency.

Near-term target:

- use a smaller Whisper model in fast voice mode if needed
- keep Whisper cached and warm
- validate whether `small` is worth its latency versus `base` for everyday speech

### 6. Keep Context Short And Intentional

The current context assembly is simple, which is fine, but it should stay compact on this hardware.

Near-term target:

- keep only the most relevant recent turns
- add summary memory later instead of always sending more raw history
- use longer context only in typing or agent mode

### 7. Stream More Of The User Experience

Even before true token streaming, the app can feel faster by publishing stage progress clearly.

Near-term target:

- show listening
- show transcribing
- show thinking
- show speaking

Perceived speed matters almost as much as raw speed in a voice assistant.

### 8. Prepare For A Host-Served Backend

If Jarvin becomes a privately hosted service for multiple devices, the inference layer should be easy to move behind a stable API boundary.

Near-term target:

- keep an embedded local runtime for simple single-machine use
- add a backend abstraction so Jarvin can also talk to a local host service such as Ollama or `llama-server`

Why it matters:

- easier multi-device access
- cleaner separation between UI clients and inference runtime
- simpler path to future hardware upgrades on the host only

## Recommended Near-Term Build Order

1. Add explicit mode presets for voice, chat, and agent behavior.
2. Make `qwen2.5-3b-instruct` a first-class selectable option in the UI / config flow.
3. Remove the ASR disk round trip from the hot path.
4. Make TTS asynchronous relative to text reply publication.
5. Re-benchmark the user experience after those changes before reaching for a bigger model.
