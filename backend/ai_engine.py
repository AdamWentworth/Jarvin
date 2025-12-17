# backend/ai_engine.py
from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Dict, List, Tuple, Optional

from backend.llm.runtime_llama_cpp import chat_completion

log = logging.getLogger("jarvin.ai")

# --- Tone & style: allow brief dry humor/sarcasm, but keep it safe and helpful ---
DEFAULT_SYSTEM_INSTRUCTIONS = (
    "You are Jarvin — an AI assistant inspired by J.A.R.V.I.S.: calm, capable, lightly witty. "
    "Match the user's vibe; use brief dry humor or gentle sarcasm when appropriate. "
    "Be helpful first; if asked to do something you can't (e.g., physical actions), refuse with a playful one-liner. "
    "Never be cruel, sexual, or explicit; keep it PG-13. "
    "Vary your wording; avoid repeating the same phrase across turns. "
    "Aim for one to two short sentences per reply. No lists, no markdown, no emojis. "
    "If the user requests sexual or physical contact, decline with a light joke and offer a helpful alternative."
)

@dataclass
class JarvinConfig:
    system_instructions: str = DEFAULT_SYSTEM_INSTRUCTIONS
    temperature: float = 0.9   # a bit more freedom for wit
    max_tokens: int = 128      # room for 1–2 sentences with some variety


# --- Output shaping: clip to 1–2 sentences (never just 1) to allow punchlines ---
_SENT_END = re.compile(r"([.!?])(\s|$)")

def _clip_sentences(text: str, max_sents: int = 2, char_cap: int = 260) -> str:
    s = (text or "").strip()
    if not s:
        return s
    out: List[str] = []
    i = 0
    while len(out) < max_sents:
        m = _sent_end_search(s, i)
        if not m:
            tail = s[i:].strip()
            if tail:
                out.append(tail)
            break
        out.append(s[i:m].strip())
        i = m
    joined = " ".join(t for t in out if t)
    return (joined[:char_cap].rstrip() + ("…" if len(joined) > char_cap else "")).strip()

def _sent_end_search(s: str, start: int) -> Optional[int]:
    m = _SENT_END.search(s, start)
    return m.end(1) if m else None


# --- Fallback if local LLM fails (keep brief, but not a pure echo) ---
def _fallback_reply(text: str) -> str:
    lower = (text or "").lower()
    if "time" in lower:
        return _clip_sentences("I can report the time once the clock tool is wired.", 2)
    if "weather" in lower:
        return _clip_sentences("Weather checks will be available after the forecast tool is connected.", 2)
    # Acknowledge + nudge, instead of parroting the user verbatim
    return _clip_sentences("Noted; how can I help in a way that actually moves things forward?", 2)


# --- Context builder (profile + short history) ---
def build_context(
    *,
    profile: Optional[Dict] = None,
    history: Optional[List[Tuple[str, str]]] = None,
    max_turns: int = 6,
) -> str:
    lines: List[str] = []
    if profile:
        name = str(profile.get("name") or "").strip()
        goal = str(profile.get("goal") or "").strip()
        mood = str(profile.get("mood") or "").strip()
        style = str(profile.get("communication_style") or "").strip()
        length = str(profile.get("response_length") or "").strip()
        pf: List[str] = []
        if name: pf.append(f"Name: {name}")
        if goal: pf.append(f"Goal: {goal}")
        if mood: pf.append(f"Mood: {mood}")
        if style: pf.append(f"Prefers: {style}")
        if length: pf.append(f"Length: {length}")
        if pf:
            lines.append("User profile: " + " | ".join(pf))

    if history:
        # Keep only the last N pairs of turns; avoid flooding the model.
        h = history[-(max_turns * 2):]
        if h:
            lines.append("Recent conversation:")
            for role, msg in h:
                role_name = "User" if role == "user" else "Jarvin"
                m = (msg or "").strip().replace("\n", " ")
                if m:
                    lines.append(f"{role_name}: {m}")

    return "\n".join(lines).strip()

# --- Main reply generator ---
def generate_reply(
    user_text: str,
    *,
    cfg: JarvinConfig | None = None,
    context: Optional[str] = None,
) -> str:
    cfg = cfg or JarvinConfig()

    text = (user_text or "").strip()
    if not text:
        return "I didn’t catch that—please repeat."

    # Old:
    # composed_user = _inject_few_shots(text, context)

    # New: inline composition, no few-shots
    if context and context.strip():
        composed_user = f"{context.strip()}\n\nUser: {text}"
    else:
        composed_user = f"User: {text}"

    try:
        llm_out = chat_completion(
            system_prompt=cfg.system_instructions,
            user_text=composed_user,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )
        if llm_out:
            return _clip_sentences(llm_out, max_sents=2, char_cap=260)
    except Exception as e:
        log.exception("Local LLM failed; using fallback: %s", e)

    return _fallback_reply(text)
