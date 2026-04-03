from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Dict, List, Tuple, Optional

from backend.llm.runtime_router import chat_completion

log = logging.getLogger("jarvin.ai")

VOICE_FAST = "voice_fast"
CHAT_BALANCED = "chat_balanced"
AGENT_STRONG = "agent_strong"
DEFAULT_CHAT_MODE = CHAT_BALANCED

_MODE_LABELS: Dict[str, str] = {
    VOICE_FAST: "Voice Fast",
    CHAT_BALANCED: "Chat Balanced",
    AGENT_STRONG: "Agent Strong",
}

_MODE_HINTS: Dict[str, str] = {
    VOICE_FAST: "Short, speakable replies tuned for conversational back-and-forth.",
    CHAT_BALANCED: "General-purpose chat with a balance of speed, context, and clarity.",
    AGENT_STRONG: "Longer, more structured replies for planning, coding, and task work.",
}

_BASE_PERSONA = (
    "You are Jarvin, a local-first AI assistant inspired by J.A.R.V.I.S.: calm, capable, and lightly witty. "
    "Match the user's vibe. Be helpful first and keep humor gentle. "
    "Never be cruel, sexual, or explicit; keep it PG-13."
)

_SYSTEM_BY_MODE: Dict[str, str] = {
    VOICE_FAST: (
        _BASE_PERSONA
        + " Reply in one or two short sentences that sound natural when spoken aloud. "
        + "Avoid markdown, lists, and rambling."
    ),
    CHAT_BALANCED: (
        _BASE_PERSONA
        + " Prefer concise, clear answers. "
        + "Short paragraphs are fine, but keep things easy to scan."
    ),
    AGENT_STRONG: (
        _BASE_PERSONA
        + " For tasks, coding, or planning work, be structured, explicit, and actionable. "
        + "Use markdown and short lists when that improves clarity."
    ),
}


@dataclass(frozen=True)
class JarvinConfig:
    mode: str = DEFAULT_CHAT_MODE
    system_instructions: str = _SYSTEM_BY_MODE[DEFAULT_CHAT_MODE]
    temperature: float = 0.8
    max_tokens: int = 192
    max_sentences: int | None = 3
    char_cap: int | None = 420
    history_window: int = 6


_MODE_PRESETS: Dict[str, JarvinConfig] = {
    VOICE_FAST: JarvinConfig(
        mode=VOICE_FAST,
        system_instructions=_SYSTEM_BY_MODE[VOICE_FAST],
        temperature=0.6,
        max_tokens=96,
        max_sentences=2,
        char_cap=240,
        history_window=4,
    ),
    CHAT_BALANCED: JarvinConfig(
        mode=CHAT_BALANCED,
        system_instructions=_SYSTEM_BY_MODE[CHAT_BALANCED],
        temperature=0.8,
        max_tokens=192,
        max_sentences=3,
        char_cap=420,
        history_window=6,
    ),
    AGENT_STRONG: JarvinConfig(
        mode=AGENT_STRONG,
        system_instructions=_SYSTEM_BY_MODE[AGENT_STRONG],
        temperature=0.35,
        max_tokens=512,
        max_sentences=None,
        char_cap=4000,
        history_window=8,
    ),
}


def normalize_mode(mode: str | None) -> str:
    value = str(mode or "").strip().lower()
    return value if value in _MODE_PRESETS else DEFAULT_CHAT_MODE


def mode_choices() -> List[str]:
    return [VOICE_FAST, CHAT_BALANCED, AGENT_STRONG]


def mode_choice_pairs() -> List[tuple[str, str]]:
    return [(_MODE_LABELS[name], name) for name in mode_choices()]


def mode_label(mode: str | None) -> str:
    return _MODE_LABELS[normalize_mode(mode)]


def mode_hint(mode: str | None) -> str:
    name = normalize_mode(mode)
    return f"**{_MODE_LABELS[name]}**: {_MODE_HINTS[name]}"


def build_jarvin_config(
    *,
    mode: str | None = None,
    system_instructions: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> JarvinConfig:
    normalized = normalize_mode(mode)
    preset = _MODE_PRESETS[normalized]
    return JarvinConfig(
        mode=normalized,
        system_instructions=system_instructions or preset.system_instructions,
        temperature=temperature if temperature is not None else preset.temperature,
        max_tokens=max_tokens if max_tokens is not None else preset.max_tokens,
        max_sentences=preset.max_sentences,
        char_cap=preset.char_cap,
        history_window=preset.history_window,
    )


_SENT_END = re.compile(r"([.!?])(\s|$)")


def _sent_end_search(s: str, start: int) -> Optional[int]:
    m = _SENT_END.search(s, start)
    return m.end(1) if m else None


def _shape_output(text: str, cfg: JarvinConfig) -> str:
    s = (text or "").strip()
    if not s:
        return s

    if cfg.max_sentences is not None:
        out: List[str] = []
        i = 0
        while len(out) < cfg.max_sentences:
            m = _sent_end_search(s, i)
            if not m:
                tail = s[i:].strip()
                if tail:
                    out.append(tail)
                break
            out.append(s[i:m].strip())
            i = m
        s = " ".join(t for t in out if t)

    if cfg.char_cap is not None and len(s) > cfg.char_cap:
        suffix = "..."
        s = s[: max(0, cfg.char_cap - len(suffix))].rstrip() + suffix

    return s.strip()


def _fallback_reply(text: str, cfg: JarvinConfig) -> str:
    lower = (text or "").lower()
    if "time" in lower:
        return _shape_output("I can report the time once the clock tool is wired.", cfg)
    if "weather" in lower:
        return _shape_output("Weather checks will be available after the forecast tool is connected.", cfg)
    return _shape_output("Noted. How can I help in a way that actually moves things forward?", cfg)


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
        if name:
            pf.append(f"Name: {name}")
        if goal:
            pf.append(f"Goal: {goal}")
        if mood:
            pf.append(f"Mood: {mood}")
        if style:
            pf.append(f"Prefers: {style}")
        if length:
            pf.append(f"Length: {length}")
        if pf:
            lines.append("User profile: " + " | ".join(pf))

    if history:
        h = history[-(max_turns * 2) :]
        if h:
            lines.append("Recent conversation:")
            for role, msg in h:
                role_name = "User" if role == "user" else "Jarvin"
                m = (msg or "").strip().replace("\n", " ")
                if m:
                    lines.append(f"{role_name}: {m}")

    return "\n".join(lines).strip()


def generate_reply(
    user_text: str,
    *,
    cfg: JarvinConfig | None = None,
    context: Optional[str] = None,
) -> str:
    cfg = cfg or build_jarvin_config()

    text = (user_text or "").strip()
    if not text:
        return "I didn't catch that. Please repeat."

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
            return _shape_output(llm_out, cfg)
    except Exception as e:
        log.exception("Local LLM failed; using fallback: %s", e)

    return _fallback_reply(text, cfg)
