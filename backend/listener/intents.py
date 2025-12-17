# backend/listener/intents.py
from __future__ import annotations
import re

# Accept a broad but sane set of shutdown phrases, including
# "kill the server" (allowing words between 'kill' and 'server').
_SHUTDOWN_HOTWORDS = re.compile(
    r"\b("
    r"shut\s*down|shutdown|power\s*off|turn\s*off|"
    r"stop\s+listening|stop\s+the\s+server|stop\s+server|"
    r"exit|quit|terminate|end\s+(?:session|process|server)|"
    r"kill\b.*\bserver\b"
    r")\b",
    re.IGNORECASE,
)

_NEGATIONS = re.compile(
    r"\b(don't|do\s+not|not\s+now|cancel|false\s+alarm)\b",
    re.IGNORECASE,
)

_CONFIRM_HOTWORDS = re.compile(
    r"\b("
    r"confirm(?:ed)?\s+(?:shut\s*down|shutdown|exit|quit)|"
    r"yes[, ]*(?:shut\s*down|exit)|"
    r"go\s+ahead"
    r")\b",
    re.IGNORECASE,
)

CONFIRM_WINDOW_SEC: float = 15.0


def intent_shutdown(text: str) -> bool:
    if _NEGATIONS.search(text):
        return False
    return bool(_SHUTDOWN_HOTWORDS.search(text))


def intent_confirm(text: str) -> bool:
    if _NEGATIONS.search(text):
        return False
    return bool(_CONFIRM_HOTWORDS.search(text))
