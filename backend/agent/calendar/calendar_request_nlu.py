from __future__ import annotations

import json
import re
from typing import Any

CALENDAR_KEYWORDS = (
    "calendar",
    "google calendar",
    "schedule",
    "agenda",
    "event",
    "events",
    "meeting",
    "meetings",
    "appointment",
    "appointments",
)

CALENDAR_FOLLOW_UP_HINTS = (
    "upcoming week",
    "this week",
    "next week",
    "upcoming",
    "going on",
    "what about",
    "how about",
    "all the events",
    "anything real",
    "what i have",
)

CALENDAR_AUTH_HINTS = ("connect", "authorize", "auth", "set up", "setup", "link")
CALENDAR_PRONOUN_HINTS = ("that", "it", "that meeting", "that event", "this meeting", "this event")
CALENDAR_LOOKUP_HINTS = (
    "look at",
    "check",
    "show",
    "tell me",
    "what do i have",
    "what's on",
    "what is on",
    "what have i got",
    "what do i have going on",
)
CALENDAR_CREATE_PREFIXES = (
    "add ",
    "create ",
    "schedule ",
    "put ",
    "please add ",
    "please create ",
    "please schedule ",
    "please put ",
)
CALENDAR_DELETE_PREFIXES = ("delete ", "remove ", "cancel ", "please delete ", "please remove ", "please cancel ")
CALENDAR_MOVE_PREFIXES = ("move ", "reschedule ", "shift ", "postpone ", "delay ", "please move ", "please reschedule ")
CALENDAR_RENAME_PREFIXES = ("rename ", "retitle ", "please rename ", "please retitle ")


def is_explicit_calendar_lookup(lower: str) -> bool:
    if looks_like_calendar_mutation(lower):
        return False
    if any(token in lower for token in ("google calendar", "my calendar", "calendar", "schedule", "agenda")):
        if any(token in lower for token in CALENDAR_LOOKUP_HINTS):
            return True
        if any(token in lower for token in ("today", "tomorrow", "this week", "next week", "upcoming", "going on")):
            return True
    return False


def looks_like_calendar_mutation(lower: str) -> bool:
    return any(
        lower.startswith(prefix)
        for prefix in (
            *CALENDAR_CREATE_PREFIXES,
            *CALENDAR_DELETE_PREFIXES,
            *CALENDAR_MOVE_PREFIXES,
            *CALENDAR_RENAME_PREFIXES,
            "set ",
            "change ",
            "update ",
            "show event details",
            "show details",
            "read event details",
            "open event details",
        )
    )


def looks_calendar_related(message: str, context: Any | None) -> bool:
    lower = message.lower()
    if any(token in lower for token in CALENDAR_KEYWORDS):
        return True
    if any(prefix in lower for prefix in ("meeting", "event", "appointment")) and looks_like_calendar_mutation(lower):
        return True
    if context is None:
        return False
    return any(token in lower for token in CALENDAR_FOLLOW_UP_HINTS) or uses_calendar_context(lower)


def infer_window_days(lower: str) -> int:
    if "tomorrow" in lower:
        return 2
    if "next week" in lower or "upcoming week" in lower or "7" in lower:
        return 7
    if "this week" in lower or "upcoming" in lower:
        return 7
    if "today" in lower:
        return 1
    return 7


def coerce_window_days(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return min(parsed, 30)


def parse_json_object(text: str) -> dict[str, object]:
    body = str(text or "").strip()
    if not body:
        return {}
    start = body.find("{")
    end = body.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(body[start : end + 1])
    except json.JSONDecodeError:
        return {}


def clean_text(value: object) -> str | None:
    cleaned = str(value or "").strip().rstrip("?.!,")
    return cleaned or None


def starts_with_any(lower: str, prefixes: tuple[str, ...]) -> bool:
    return any(lower.startswith(prefix) for prefix in prefixes)


def uses_calendar_context(lower: str) -> bool:
    return any(token in lower for token in CALENDAR_PRONOUN_HINTS)


def strip_calendar_create_prefix(message: str) -> str | None:
    for prefix in CALENDAR_CREATE_PREFIXES:
        if message.lower().startswith(prefix):
            return clean_text(message[len(prefix) :])
    return clean_text(message)


def looks_like_calendar_details(lower: str, *, context: Any | None) -> bool:
    return any(phrase in lower for phrase in ("show event details", "show details", "read event details", "open event details")) or (
        context is not None and "details" in lower and uses_calendar_context(lower)
    )


def extract_details_query(message: str) -> str | None:
    stripped = re.sub(r"^(show|read|open)\s+(event\s+)?details\s+(for\s+)?", "", message, flags=re.IGNORECASE)
    return strip_calendar_tail(clean_text(stripped))


def looks_like_calendar_delete(lower: str, *, context: Any | None) -> bool:
    return starts_with_any(lower, CALENDAR_DELETE_PREFIXES) or (context is not None and uses_calendar_context(lower) and "delete" in lower)


def extract_delete_query(message: str, *, context: Any | None) -> str | None:
    if context is not None and uses_calendar_context(message.lower()):
        return context.last_query
    lowered = message.lower()
    prefix = next((candidate for candidate in CALENDAR_DELETE_PREFIXES if lowered.startswith(candidate)), "")
    return strip_calendar_tail(clean_text(message[len(prefix) :])) if prefix else strip_calendar_tail(clean_text(message))


def looks_like_calendar_move(lower: str, *, context: Any | None) -> bool:
    if starts_with_any(lower, CALENDAR_MOVE_PREFIXES):
        return True
    return context is not None and uses_calendar_context(lower) and any(token in lower for token in ("move", "reschedule", "shift", "push", "delay", "postpone", "back an hour"))


def extract_move_parts(message: str, *, context: Any | None) -> tuple[str | None, str | None]:
    lowered = message.lower()
    if context is not None and uses_calendar_context(lowered):
        reference = context.last_query
        if " to " in lowered:
            _, _, tail = message.partition(" to ")
            return reference, strip_calendar_tail(clean_text(tail))
        if " back " in lowered:
            _, _, tail = message.partition(" back ")
            return reference, strip_calendar_tail(clean_text(f"back {tail}"))
        return reference, strip_calendar_tail(clean_text(message))

    prefix = next((candidate for candidate in CALENDAR_MOVE_PREFIXES if lowered.startswith(candidate)), "")
    body = message[len(prefix) :] if prefix else message
    if " to " in body:
        query, _, when_text = body.partition(" to ")
        return strip_calendar_tail(clean_text(query)), strip_calendar_tail(clean_text(when_text))
    if " back " in body:
        query, _, offset_text = body.partition(" back ")
        return strip_calendar_tail(clean_text(query)), strip_calendar_tail(clean_text(f"back {offset_text}"))
    return strip_calendar_tail(clean_text(body)), None


def looks_like_calendar_rename(lower: str, *, context: Any | None) -> bool:
    return starts_with_any(lower, CALENDAR_RENAME_PREFIXES) or (
        context is not None and uses_calendar_context(lower) and ("rename" in lower or "retitle" in lower)
    )


def extract_rename_parts(message: str, *, context: Any | None) -> tuple[str | None, str | None]:
    lowered = message.lower()
    if context is not None and uses_calendar_context(lowered):
        if " to " in message:
            _, _, new_title = message.partition(" to ")
            return context.last_query, strip_calendar_tail(clean_text(new_title))
        return context.last_query, None

    prefix = next((candidate for candidate in CALENDAR_RENAME_PREFIXES if lowered.startswith(candidate)), "")
    body = message[len(prefix) :] if prefix else message
    query, _, new_title = body.partition(" to ")
    return strip_calendar_tail(clean_text(query)), strip_calendar_tail(clean_text(new_title))


def looks_like_calendar_location_update(lower: str, *, context: Any | None) -> bool:
    if "location" in lower and any(token in lower for token in ("change", "update", "set", "make")):
        return True
    return context is not None and uses_calendar_context(lower) and "location" in lower


def extract_location_parts(message: str, *, context: Any | None) -> tuple[str | None, str | None]:
    lowered = message.lower()
    if lowered.startswith("make ") and " location for " in lowered:
        match = re.match(r"^(?:please\s+)?make\s+(.+?)\s+the\s+location\s+for\s+(.+)$", message, flags=re.IGNORECASE)
        if match:
            raw_location, raw_query = match.groups()
            query = context.last_query if context is not None and uses_calendar_context(raw_query.lower()) else clean_text(raw_query)
            return query, clean_text(raw_location)

    if context is not None and uses_calendar_context(lowered):
        if " to " in message:
            _, _, value = message.partition(" to ")
            return context.last_query, clean_text(value)
        if " as " in message:
            _, _, value = message.partition(" as ")
            return context.last_query, clean_text(value)
        return context.last_query, clean_text(message)

    normalized = re.sub(r"^(change|update|set|make)\s+(the\s+)?location\s+(of\s+)?", "", message, flags=re.IGNORECASE)
    query = normalized
    new_location: str | None = None
    for marker in (" to ", " as "):
        if marker in normalized:
            query, _, new_location = normalized.partition(marker)
            break
    return strip_calendar_tail(clean_text(query)), strip_calendar_tail(clean_text(new_location))


def looks_like_calendar_notes_update(lower: str, *, context: Any | None) -> bool:
    if any(token in lower for token in ("notes", "description", "details")) and any(token in lower for token in ("update", "change", "set", "add")):
        return True
    return context is not None and uses_calendar_context(lower) and any(token in lower for token in ("notes", "description"))


def extract_notes_parts(message: str, *, context: Any | None) -> tuple[str | None, str | None]:
    lowered = message.lower()
    if context is not None and uses_calendar_context(lowered):
        if " to " in message:
            _, _, value = message.partition(" to ")
            return context.last_query, clean_text(value)
        return context.last_query, clean_text(message)

    normalized = re.sub(
        r"^(update|change|set|add)\s+(the\s+)?(notes|description|details)\s+(for\s+)?",
        "",
        message,
        flags=re.IGNORECASE,
    )
    query = normalized
    description: str | None = None
    if " to " in normalized:
        query, _, description = normalized.partition(" to ")
    return strip_calendar_tail(clean_text(query)), clean_text(description)


def strip_calendar_tail(value: str | None) -> str | None:
    if not value:
        return value
    lowered = value.lower()
    for suffix in (" on my calendar", " from my calendar", " in my calendar"):
        if lowered.endswith(suffix):
            return value[: -len(suffix)].strip()
    return value
