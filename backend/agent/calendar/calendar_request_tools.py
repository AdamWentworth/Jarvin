from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from backend.ai_engine import build_jarvin_config, generate_reply
from backend.agent.calendar.calendar_request_nlu import (
    CALENDAR_AUTH_HINTS,
    CALENDAR_FOLLOW_UP_HINTS,
    clean_text,
    coerce_window_days,
    extract_delete_query,
    extract_details_query,
    extract_location_parts,
    extract_move_parts,
    extract_notes_parts,
    extract_rename_parts,
    infer_window_days,
    is_explicit_calendar_lookup,
    looks_calendar_related,
    looks_like_calendar_delete,
    looks_like_calendar_details,
    looks_like_calendar_location_update,
    looks_like_calendar_move,
    looks_like_calendar_notes_update,
    looks_like_calendar_rename,
    parse_json_object,
    strip_calendar_create_prefix,
)


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

    if not looks_calendar_related(message, context):
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

    if any(token in lower for token in CALENDAR_AUTH_HINTS) and "calendar" in lower:
        return CalendarPlan(is_calendar_request=True, action="auth")

    if is_explicit_calendar_lookup(lower):
        return CalendarPlan(
            is_calendar_request=True,
            action="lookup",
            window_days=infer_window_days(lower),
        )

    if context is not None and any(token in lower for token in CALENDAR_FOLLOW_UP_HINTS):
        return CalendarPlan(
            is_calendar_request=True,
            action="lookup",
            window_days=infer_window_days(lower),
        )

    if "calendar" in lower or "event" in lower:
        details = strip_calendar_create_prefix(message)
        if details and any(lower.startswith(prefix) for prefix in ("add ", "create ", "schedule ", "put ", "please add ", "please create ", "please schedule ", "please put ")):
            return CalendarPlan(is_calendar_request=True, action="create", query=details)

    if looks_like_calendar_details(lower, context=context):
        return CalendarPlan(is_calendar_request=True, action="details", query=extract_details_query(message))

    if looks_like_calendar_delete(lower, context=context):
        return CalendarPlan(is_calendar_request=True, action="delete", query=extract_delete_query(message, context=context))

    if looks_like_calendar_move(lower, context=context):
        query, when_text = extract_move_parts(message, context=context)
        return CalendarPlan(is_calendar_request=True, action="move", query=query, when_text=when_text)

    if looks_like_calendar_rename(lower, context=context):
        query, new_title = extract_rename_parts(message, context=context)
        return CalendarPlan(is_calendar_request=True, action="rename", query=query, new_title=new_title)

    if looks_like_calendar_location_update(lower, context=context):
        query, new_location = extract_location_parts(message, context=context)
        return CalendarPlan(
            is_calendar_request=True,
            action="update_location",
            query=query,
            new_location=new_location,
        )

    if looks_like_calendar_notes_update(lower, context=context):
        query, new_description = extract_notes_parts(message, context=context)
        return CalendarPlan(
            is_calendar_request=True,
            action="update_description",
            query=query,
            new_description=new_description,
        )

    return None


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
    data = parse_json_object(raw)
    return CalendarPlan(
        is_calendar_request=bool(data.get("is_calendar_request")),
        action=str(data.get("action") or "unknown").strip().lower(),
        query=clean_text(data.get("query")),
        when_text=clean_text(data.get("when_text")),
        new_title=clean_text(data.get("new_title")),
        new_location=clean_text(data.get("new_location")),
        new_description=clean_text(data.get("new_description")),
        window_days=coerce_window_days(data.get("window_days")),
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

