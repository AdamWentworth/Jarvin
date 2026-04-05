from __future__ import annotations

import re

_FOLLOW_UP_PRONOUN_RE = re.compile(r"\b(?:that|it|this|those|them)\b", re.IGNORECASE)
_FOLLOW_UP_TIME_RE = re.compile(
    r"\b(?:today|tomorrow|tonight|morning|afternoon|evening|noon|midnight|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?|\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b",
    re.IGNORECASE,
)

_ACTIVE_DOMAIN_CUES: dict[str, tuple[str, ...]] = {
    "weather": ("weather", "forecast", "rain", "temperature", "degrees", "outside", "umbrella"),
    "brief": ("brief", "rundown", "my day", "day look like", "daily brief", "morning brief"),
    "reminder": ("remind", "reminder", "task", "todo", "to-do", "routine"),
    "calendar": ("calendar", "agenda", "schedule", "meeting", "event", "appointment"),
    "workspace": ("repo", "repository", "codebase", "workspace", "directory", "folder", "git", "pytest", "file"),
    "research": ("research", "search the web", "look up", "look into", "dig into", "sources", "google "),
}
_AMBIGUOUS_FOLLOW_UP_PREFIXES = (
    "how about",
    "what about",
    "and tomorrow",
    "and today",
    "for tomorrow",
    "for today",
    "show me more",
    "show more",
    "continue",
    "keep going",
    "what else",
    "summarize that",
    "compare those",
    "compare the sources",
    "run that again",
    "run that",
    "do that again",
    "open that",
    "read that",
    "show that",
    "move that",
    "push that",
    "shift that",
    "rename that",
    "update that",
    "delete that",
    "remove that",
    "cancel that",
    "mark that",
)
_AMBIGUOUS_SHORT_FOLLOW_UPS = {
    "today",
    "tomorrow",
    "tonight",
    "later",
    "earlier",
    "back an hour",
    "back 1 hour",
}


def looks_like_ambiguous_follow_up(message: str) -> bool:
    lower = str(message or "").strip().lower()
    if not lower:
        return False
    if lower in _AMBIGUOUS_SHORT_FOLLOW_UPS:
        return True
    if any(lower.startswith(prefix) for prefix in _AMBIGUOUS_FOLLOW_UP_PREFIXES):
        return True
    if len(lower.split()) <= 8 and _FOLLOW_UP_TIME_RE.search(lower):
        return True
    if len(lower.split()) <= 10 and _FOLLOW_UP_PRONOUN_RE.search(lower):
        return True
    return False


def has_conflicting_domain_cues(message: str, *, active_domain: str) -> bool:
    lower = str(message or "").strip().lower()
    for domain, cues in _ACTIVE_DOMAIN_CUES.items():
        if domain == active_domain:
            continue
        if any(cue in lower for cue in cues):
            return True
    return False
