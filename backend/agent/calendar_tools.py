from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from backend.ai_engine import build_jarvin_config, generate_reply

_CALENDAR_KEYWORDS = (
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

_CALENDAR_FOLLOW_UP_HINTS = (
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

_CALENDAR_AUTH_HINTS = ("connect", "authorize", "auth", "set up", "setup", "link")
_CALENDAR_PRONOUN_HINTS = ("that", "it", "that meeting", "that event", "this meeting", "this event")
_CALENDAR_LOOKUP_HINTS = (
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
_CALENDAR_CREATE_PREFIXES = (
    "add ",
    "create ",
    "schedule ",
    "put ",
    "please add ",
    "please create ",
    "please schedule ",
    "please put ",
)
_CALENDAR_DELETE_PREFIXES = ("delete ", "remove ", "cancel ", "please delete ", "please remove ", "please cancel ")
_CALENDAR_MOVE_PREFIXES = ("move ", "reschedule ", "shift ", "postpone ", "delay ", "please move ", "please reschedule ")
_CALENDAR_RENAME_PREFIXES = ("rename ", "retitle ", "please rename ", "please retitle ")


@dataclass(frozen=True)
class CalendarPlan:
    is_calendar_request: bool
    action: str = "lookup"
    query: str | None = None
    when_text: str | None = None
    new_title: str | None = None
    new_location: str | None = None
    new_description: str | None = None
    window_days: int | None = None


@dataclass(frozen=True)
class CalendarConversationContext:
    last_action: str = "lookup"
    last_query: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=15))


_calendar_context: dict[str, CalendarConversationContext] = {}


def maybe_plan_calendar_request(text: str, *, conversation_id: int | None = None) -> CalendarPlan | None:
    message = (text or "").strip()
    if not message:
        return None

    context = get_calendar_context(conversation_id)
    heuristic = _heuristic_plan(message, context)
    if heuristic is not None:
        _remember_calendar_context(conversation_id, heuristic)
        return heuristic

    if not _looks_calendar_related(message, context):
        return None

    plan = _llm_plan_calendar_request(message, context=context)
    if not plan.is_calendar_request:
        return None
    plan = _resolve_contextual_references(plan, context=context)
    _remember_calendar_context(conversation_id, plan)
    return plan


def get_calendar_context(conversation_id: int | None) -> CalendarConversationContext | None:
    key = _context_key(conversation_id)
    context = _calendar_context.get(key)
    if context is None:
        return None
    if context.expires_at <= datetime.now(timezone.utc):
        _calendar_context.pop(key, None)
        return None
    return context


def _remember_calendar_context(conversation_id: int | None, plan: CalendarPlan) -> None:
    _calendar_context[_context_key(conversation_id)] = CalendarConversationContext(
        last_action=plan.action or "lookup",
        last_query=plan.query,
    )


def _context_key(conversation_id: int | None) -> str:
    return str(conversation_id) if conversation_id is not None else "__default__"


def _heuristic_plan(message: str, context: CalendarConversationContext | None) -> CalendarPlan | None:
    lower = message.lower()

    if any(token in lower for token in _CALENDAR_AUTH_HINTS) and "calendar" in lower:
        return CalendarPlan(is_calendar_request=True, action="auth")

    if _is_explicit_calendar_lookup(lower):
        return CalendarPlan(
            is_calendar_request=True,
            action="lookup",
            window_days=_infer_window_days(lower),
        )

    if context is not None and any(token in lower for token in _CALENDAR_FOLLOW_UP_HINTS):
        return CalendarPlan(
            is_calendar_request=True,
            action="lookup",
            window_days=_infer_window_days(lower),
        )

    if _starts_with_any(lower, _CALENDAR_CREATE_PREFIXES) and ("calendar" in lower or "event" in lower):
        details = _strip_calendar_create_prefix(message)
        if details:
            return CalendarPlan(is_calendar_request=True, action="create", query=details)

    if _looks_like_calendar_details(lower, context=context):
        query = _extract_details_query(message)
        return CalendarPlan(is_calendar_request=True, action="details", query=query)

    if _looks_like_calendar_delete(lower, context=context):
        query = _extract_delete_query(message, context=context)
        return CalendarPlan(is_calendar_request=True, action="delete", query=query)

    if _looks_like_calendar_move(lower, context=context):
        query, when_text = _extract_move_parts(message, context=context)
        return CalendarPlan(is_calendar_request=True, action="move", query=query, when_text=when_text)

    if _looks_like_calendar_rename(lower, context=context):
        query, new_title = _extract_rename_parts(message, context=context)
        return CalendarPlan(is_calendar_request=True, action="rename", query=query, new_title=new_title)

    if _looks_like_calendar_location_update(lower, context=context):
        query, new_location = _extract_location_parts(message, context=context)
        return CalendarPlan(
            is_calendar_request=True,
            action="update_location",
            query=query,
            new_location=new_location,
        )

    if _looks_like_calendar_notes_update(lower, context=context):
        query, new_description = _extract_notes_parts(message, context=context)
        return CalendarPlan(
            is_calendar_request=True,
            action="update_description",
            query=query,
            new_description=new_description,
        )

    return None


def _is_explicit_calendar_lookup(lower: str) -> bool:
    if _looks_like_calendar_mutation(lower):
        return False
    if any(token in lower for token in ("google calendar", "my calendar", "calendar", "schedule", "agenda")):
        if any(token in lower for token in _CALENDAR_LOOKUP_HINTS):
            return True
        if any(token in lower for token in ("today", "tomorrow", "this week", "next week", "upcoming", "going on")):
            return True
    return False


def _looks_like_calendar_mutation(lower: str) -> bool:
    return any(
        lower.startswith(prefix)
        for prefix in (
            *_CALENDAR_CREATE_PREFIXES,
            *_CALENDAR_DELETE_PREFIXES,
            *_CALENDAR_MOVE_PREFIXES,
            *_CALENDAR_RENAME_PREFIXES,
            "set ",
            "change ",
            "update ",
            "show event details",
            "show details",
            "read event details",
            "open event details",
        )
    )


def _looks_calendar_related(message: str, context: CalendarConversationContext | None) -> bool:
    lower = message.lower()
    if any(token in lower for token in _CALENDAR_KEYWORDS):
        return True
    if any(prefix in lower for prefix in ("meeting", "event", "appointment")) and _looks_like_calendar_mutation(lower):
        return True
    if context is None:
        return False
    return any(token in lower for token in _CALENDAR_FOLLOW_UP_HINTS) or _uses_calendar_context(lower)


def _llm_plan_calendar_request(message: str, *, context: CalendarConversationContext | None) -> CalendarPlan:
    system = (
        "You extract Google Calendar tool arguments for Jarvin. "
        "Return JSON only with keys: "
        "is_calendar_request (boolean), action (string), query (string|null), "
        "when_text (string|null), new_title (string|null), new_location (string|null), "
        "new_description (string|null), window_days (integer|null). "
        "Valid actions are lookup, auth, create, details, delete, rename, update_location, update_description, move, unknown. "
        "Treat 'Google Calendar' as the user's calendar, not as web search. "
        "For requests like 'look at my calendar today' or 'what do I have this week', action should be lookup. "
        "For follow-up phrases like 'how about this week' after prior calendar context, still treat it as calendar lookup. "
        "For edit requests, extract the current event reference into query and the requested change into the appropriate field. "
        "For phrases like 'shift lunch back an hour', action should be move and when_text can be 'back an hour'. "
        "For phrases like 'make the cafe the location for that meeting', action should be update_location. "
        "If the user refers to a prior event with 'it' or 'that', query may be null so Jarvin can use context. "
        "Do not answer the calendar question itself."
    )
    prompt = (
        f"Recent calendar context:\n"
        f"last_action={context.last_action if context else ''}\n"
        f"last_query={context.last_query if context else ''}\n\n"
        f"User message:\n{message}"
    )
    cfg_obj = build_jarvin_config(
        mode="agent_strong",
        system_instructions=system,
        temperature=0.1,
        max_tokens=220,
    )
    raw = generate_reply(prompt, cfg=cfg_obj, context=None)
    data = _parse_json_object(raw)
    return CalendarPlan(
        is_calendar_request=bool(data.get("is_calendar_request")),
        action=str(data.get("action") or "unknown").strip().lower(),
        query=_strip_calendar_tail(_clean_text(data.get("query"))),
        when_text=_strip_calendar_tail(_clean_text(data.get("when_text"))),
        new_title=_strip_calendar_tail(_clean_text(data.get("new_title"))),
        new_location=_strip_calendar_tail(_clean_text(data.get("new_location"))),
        new_description=_clean_text(data.get("new_description")),
        window_days=_coerce_window_days(data.get("window_days")),
    )


def _resolve_contextual_references(plan: CalendarPlan, *, context: CalendarConversationContext | None) -> CalendarPlan:
    if context is None:
        return plan
    query = plan.query or None
    if not query and plan.action in {"details", "delete", "rename", "update_location", "update_description", "move"}:
        query = context.last_query
    return CalendarPlan(
        is_calendar_request=plan.is_calendar_request,
        action=plan.action,
        query=query,
        when_text=plan.when_text,
        new_title=plan.new_title,
        new_location=plan.new_location,
        new_description=plan.new_description,
        window_days=plan.window_days,
    )


def _infer_window_days(lower: str) -> int:
    stripped = lower.strip()
    if stripped.isdigit():
        return max(1, int(stripped))
    if "today" in lower:
        return 1
    if "tomorrow" in lower:
        return 2
    if "next week" in lower or "this week" in lower or "upcoming week" in lower:
        return 7
    match = re.search(r"next\s+(\d+)\s+days?", lower)
    if match:
        return max(1, int(match.group(1)))
    return 7


def _coerce_window_days(value: object) -> int | None:
    if value in (None, "", False):
        return None
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return None


def _parse_json_object(text: str) -> dict[str, object]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}


def _clean_text(value: object) -> str | None:
    cleaned = str(value or "").strip().rstrip("?.!,")
    return cleaned or None


def _starts_with_any(lower: str, prefixes: tuple[str, ...]) -> bool:
    return any(lower.startswith(prefix) for prefix in prefixes)


def _uses_calendar_context(lower: str) -> bool:
    return any(token in lower for token in _CALENDAR_FOLLOW_UP_HINTS) or any(token in lower for token in _CALENDAR_PRONOUN_HINTS) or _looks_like_calendar_mutation(lower)


def _strip_calendar_create_prefix(message: str) -> str | None:
    candidate = re.sub(r"^(?:please\s+)?(?:add|create|schedule|put)\s+", "", message, flags=re.IGNORECASE)
    candidate = re.sub(r"\s+(?:to|on|in)\s+(?:my\s+)?calendar\b", "", candidate, flags=re.IGNORECASE).strip()
    cleaned = _clean_text(candidate)
    return cleaned or None


def _looks_like_calendar_details(lower: str, *, context: CalendarConversationContext | None) -> bool:
    if any(token in lower for token in ("show event details", "show details", "read event details", "open event details")):
        return True
    return context is not None and any(token in lower for token in _CALENDAR_PRONOUN_HINTS) and "details" in lower


def _extract_details_query(message: str) -> str | None:
    candidate = re.sub(
        r"^(?:show|read|open|view)\s+(?:me\s+)?(?:event(?:\s+details)?|details(?:\s+for)?)\s+",
        "",
        message,
        flags=re.IGNORECASE,
    )
    candidate = re.sub(r"\s+(?:on|in)\s+(?:my\s+)?calendar\b", "", candidate, flags=re.IGNORECASE)
    return _clean_text(candidate)


def _looks_like_calendar_delete(lower: str, *, context: CalendarConversationContext | None) -> bool:
    if _starts_with_any(lower, _CALENDAR_DELETE_PREFIXES) and ("calendar" in lower or "meeting" in lower or "event" in lower or "appointment" in lower):
        return True
    return context is not None and _starts_with_any(lower, _CALENDAR_DELETE_PREFIXES) and any(token in lower for token in _CALENDAR_PRONOUN_HINTS)


def _extract_delete_query(message: str, *, context: CalendarConversationContext | None) -> str | None:
    candidate = re.sub(r"^(?:please\s+)?(?:delete|remove|cancel)\s+", "", message, flags=re.IGNORECASE)
    candidate = re.sub(r"\s+(?:from|on|in)\s+(?:my\s+)?calendar\b", "", candidate, flags=re.IGNORECASE).strip()
    cleaned = _clean_text(candidate)
    if cleaned and cleaned.lower() not in _CALENDAR_PRONOUN_HINTS:
        return cleaned
    return context.last_query if context else None


def _looks_like_calendar_move(lower: str, *, context: CalendarConversationContext | None) -> bool:
    if _starts_with_any(lower, _CALENDAR_MOVE_PREFIXES) and ("calendar" in lower or "meeting" in lower or "event" in lower or "appointment" in lower):
        return True
    if context is None:
        return False
    return _starts_with_any(lower, _CALENDAR_MOVE_PREFIXES) and (any(token in lower for token in _CALENDAR_PRONOUN_HINTS) or "back " in lower or "later" in lower or "earlier" in lower)


def _extract_move_parts(message: str, *, context: CalendarConversationContext | None) -> tuple[str | None, str | None]:
    candidate = re.sub(r"^(?:please\s+)?(?:move|reschedule|shift|postpone|delay)\s+", "", message, flags=re.IGNORECASE).strip()
    lower_candidate = candidate.lower()
    if any(token in lower_candidate for token in (" back ", " later", " earlier", " up ", " by ")):
        relative_match = re.match(
            r"(?P<query>.+?)\s+(?P<when>(?:back|later|earlier|up|by)\b.+)$",
            candidate,
            flags=re.IGNORECASE,
        )
        if relative_match:
            cleaned_query = _strip_calendar_tail(_clean_text(relative_match.group("query")))
            if cleaned_query and cleaned_query.lower() in _CALENDAR_PRONOUN_HINTS:
                cleaned_query = context.last_query if context else None
            return cleaned_query, _strip_calendar_tail(_clean_text(relative_match.group("when")))
        lowered = candidate.lower()
        for pronoun in _CALENDAR_PRONOUN_HINTS:
            if lowered.startswith(pronoun):
                trimmed = candidate[len(pronoun):].strip()
                return (context.last_query if context else None), _strip_calendar_tail(_clean_text(trimmed))
        return (context.last_query if context else None), _strip_calendar_tail(_clean_text(candidate))
    pieces = re.split(r"\bto\b", candidate, maxsplit=1, flags=re.IGNORECASE)
    if len(pieces) == 2:
        raw_query, raw_when = pieces
        cleaned_query = _strip_calendar_tail(_clean_text(raw_query))
        if cleaned_query and cleaned_query.lower() in _CALENDAR_PRONOUN_HINTS:
            cleaned_query = context.last_query if context else None
        return cleaned_query, _strip_calendar_tail(_clean_text(raw_when))
    if context is not None:
        return context.last_query, _strip_calendar_tail(_clean_text(candidate))
    return None, None


def _looks_like_calendar_rename(lower: str, *, context: CalendarConversationContext | None) -> bool:
    if _starts_with_any(lower, _CALENDAR_RENAME_PREFIXES):
        return True
    if "title" in lower and any(token in lower for token in ("set ", "change ", "update ")):
        return True
    return context is not None and any(token in lower for token in _CALENDAR_PRONOUN_HINTS) and "rename" in lower


def _extract_rename_parts(message: str, *, context: CalendarConversationContext | None) -> tuple[str | None, str | None]:
    candidate = re.sub(r"^(?:please\s+)?(?:rename|retitle)\s+", "", message, flags=re.IGNORECASE)
    if candidate == message:
        candidate = re.sub(r"^(?:please\s+)?(?:set|change|update)\s+(?:the\s+)?title\s+(?:of|for)\s+", "", message, flags=re.IGNORECASE)
    pieces = re.split(r"\b(?:to|as)\b", candidate, maxsplit=1, flags=re.IGNORECASE)
    if len(pieces) != 2:
        return context.last_query if context else None, None
    raw_query, raw_title = pieces
    cleaned_query = _strip_calendar_tail(_clean_text(raw_query))
    if cleaned_query and cleaned_query.lower() in _CALENDAR_PRONOUN_HINTS:
        cleaned_query = context.last_query if context else None
    return cleaned_query, _strip_calendar_tail(_clean_text(raw_title))


def _looks_like_calendar_location_update(lower: str, *, context: CalendarConversationContext | None) -> bool:
    if "location" in lower and any(token in lower for token in ("set ", "change ", "update ", "clear ", "remove ", "delete ", "make ")):
        return True
    if context is None:
        return False
    return any(token in lower for token in _CALENDAR_PRONOUN_HINTS) and ("location" in lower or "zoom" in lower or "meet at" in lower)


def _extract_location_parts(message: str, *, context: CalendarConversationContext | None) -> tuple[str | None, str | None]:
    lower = message.lower()
    if any(token in lower for token in ("clear location", "remove location", "delete location")):
        candidate = re.sub(
            r"^(?:please\s+)?(?:clear|remove|delete)\s+(?:the\s+)?location\s+(?:of|from)?\s*",
            "",
            message,
            flags=re.IGNORECASE,
        )
        cleaned_query = _clean_text(re.sub(r"\s+(?:on|in)\s+(?:my\s+)?calendar\b", "", candidate, flags=re.IGNORECASE))
        if cleaned_query and cleaned_query.lower() in _CALENDAR_PRONOUN_HINTS:
            cleaned_query = context.last_query if context else None
        return cleaned_query, ""

    if lower.startswith("make "):
        pieces = re.split(r"\bthe location for\b", message, maxsplit=1, flags=re.IGNORECASE)
        if len(pieces) == 2:
            raw_location = re.sub(r"^(?:please\s+)?make\s+", "", pieces[0], flags=re.IGNORECASE)
            raw_query = pieces[1]
            cleaned_query = _strip_calendar_tail(_clean_text(raw_query))
            if cleaned_query and cleaned_query.lower() in _CALENDAR_PRONOUN_HINTS:
                cleaned_query = context.last_query if context else None
            return cleaned_query, _strip_calendar_tail(_clean_text(raw_location))

    candidate = re.sub(
        r"^(?:please\s+)?(?:set|change|update)\s+(?:the\s+)?location\s+(?:of|for)\s+",
        "",
        message,
        flags=re.IGNORECASE,
    )
    parts = re.split(r"\bto\b", candidate, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) == 2:
        raw_query, raw_location = parts
        cleaned_query = _strip_calendar_tail(_clean_text(raw_query))
        if cleaned_query and cleaned_query.lower() in _CALENDAR_PRONOUN_HINTS:
            cleaned_query = context.last_query if context else None
        return cleaned_query, _strip_calendar_tail(_clean_text(raw_location))
    return context.last_query if context else None, None


def _looks_like_calendar_notes_update(lower: str, *, context: CalendarConversationContext | None) -> bool:
    if any(token in lower for token in ("notes", "description")) and any(action in lower for action in ("set ", "change ", "update ", "clear ", "remove ", "delete ")):
        return True
    return context is not None and any(token in lower for token in _CALENDAR_PRONOUN_HINTS) and "notes" in lower


def _extract_notes_parts(message: str, *, context: CalendarConversationContext | None) -> tuple[str | None, str | None]:
    lower = message.lower()
    if any(token in lower for token in ("clear notes", "remove notes", "delete notes", "clear description", "remove description", "delete description")):
        candidate = re.sub(
            r"^(?:please\s+)?(?:clear|remove|delete)\s+(?:the\s+)?(?:notes|description)\s+(?:of|from)?\s*",
            "",
            message,
            flags=re.IGNORECASE,
        )
        cleaned_query = _clean_text(re.sub(r"\s+(?:on|in)\s+(?:my\s+)?calendar\b", "", candidate, flags=re.IGNORECASE))
        if cleaned_query and cleaned_query.lower() in _CALENDAR_PRONOUN_HINTS:
            cleaned_query = context.last_query if context else None
        return cleaned_query, ""

    candidate = re.sub(
        r"^(?:please\s+)?(?:set|change|update)\s+(?:the\s+)?(?:notes|description)\s+(?:of|for)\s+",
        "",
        message,
        flags=re.IGNORECASE,
    )
    parts = re.split(r"\bto\b", candidate, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) == 2:
        raw_query, raw_notes = parts
        cleaned_query = _strip_calendar_tail(_clean_text(raw_query))
        if cleaned_query and cleaned_query.lower() in _CALENDAR_PRONOUN_HINTS:
            cleaned_query = context.last_query if context else None
        return cleaned_query, _clean_text(raw_notes)
    return context.last_query if context else None, None


def _strip_calendar_tail(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    stripped = re.sub(r"\s+(?:on|in|from|to)\s+(?:my\s+)?calendar\b$", "", cleaned, flags=re.IGNORECASE).strip()
    return stripped or None
