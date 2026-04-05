from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from backend.ai_engine import build_jarvin_config, generate_reply

_REMINDER_KEYWORDS = (
    "remind",
    "reminder",
    "task",
    "tasks",
    "to-do",
    "todo",
    "to do",
    "routine",
    "routines",
    "nudge",
    "don't let me forget",
    "dont let me forget",
    "remember to",
    "make sure i remember",
    "what do i need to do",
)

_LIST_HINTS = (
    "what do i need to do",
    "what's on my reminders",
    "what is on my reminders",
    "show my reminders",
    "show me my reminders",
    "list my reminders",
    "show my tasks",
    "show me my tasks",
    "list my tasks",
    "show my to-dos",
    "show me my to-dos",
    "show my todos",
    "show me my todos",
)

_ROUTINE_HINTS = (
    "what are my routines",
    "what's my routine",
    "what is my routine",
    "show my routines",
    "show me my routines",
    "list my routines",
)

_PRONOUN_REFERENCES = ("that", "it", "that reminder", "this reminder", "that task", "this task")
_ACTION_PREFIXES = {
    "complete": ("mark", "complete", "finish"),
    "delete": ("delete", "remove", "cancel"),
    "move": ("move", "reschedule", "delay", "postpone", "push", "shift"),
}


@dataclass(frozen=True)
class ReminderPlan:
    is_reminder_request: bool
    action: str = "unknown"
    title: str | None = None
    query: str | None = None
    when_text: str | None = None
    due_at_iso: str | None = None
    recurrence: str | None = None
    window: str | None = None


@dataclass(frozen=True)
class ReminderConversationContext:
    last_action: str = "unknown"
    last_title: str | None = None
    awaiting_time_title: str | None = None
    awaiting_time_recurrence: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=15))


_reminder_context: dict[str, ReminderConversationContext] = {}


def maybe_plan_reminder_request(text: str, *, conversation_id: int | None = None) -> ReminderPlan | None:
    message = (text or "").strip()
    if not message:
        return None

    context = get_reminder_context(conversation_id)
    heuristic = _heuristic_plan(message, context=context)
    if heuristic is not None:
        return heuristic

    if not _looks_reminder_related(message, context=context):
        return None

    plan = _llm_plan_reminder_request(message, context=context)
    if not plan.is_reminder_request:
        return None
    return _resolve_contextual_references(plan, context=context)


def get_reminder_context(conversation_id: int | None) -> ReminderConversationContext | None:
    key = _context_key(conversation_id)
    context = _reminder_context.get(key)
    if context is None:
        return None
    if context.expires_at <= datetime.now(timezone.utc):
        _reminder_context.pop(key, None)
        return None
    return context


def remember_reminder_context(
    conversation_id: int | None,
    *,
    action: str,
    last_title: str | None = None,
    awaiting_time_title: str | None = None,
    awaiting_time_recurrence: str | None = None,
) -> None:
    _reminder_context[_context_key(conversation_id)] = ReminderConversationContext(
        last_action=action or "unknown",
        last_title=last_title,
        awaiting_time_title=awaiting_time_title,
        awaiting_time_recurrence=awaiting_time_recurrence,
    )


def clear_reminder_context(conversation_id: int | None) -> None:
    _reminder_context.pop(_context_key(conversation_id), None)


def _context_key(conversation_id: int | None) -> str:
    return str(conversation_id) if conversation_id is not None else "__default__"


def _heuristic_plan(message: str, *, context: ReminderConversationContext | None) -> ReminderPlan | None:
    lower = message.lower().strip()

    if context and context.awaiting_time_title and _looks_like_due_follow_up(lower):
        return ReminderPlan(
            is_reminder_request=True,
            action="create",
            title=context.awaiting_time_title,
            when_text=message,
            recurrence=context.awaiting_time_recurrence or "once",
        )

    if any(hint in lower for hint in _ROUTINE_HINTS):
        return ReminderPlan(is_reminder_request=True, action="list_routines", window="upcoming")

    if any(hint in lower for hint in _LIST_HINTS):
        return ReminderPlan(is_reminder_request=True, action="list", window=_infer_window(lower))

    if context and context.last_title and any(reference in lower for reference in _PRONOUN_REFERENCES):
        for action, prefixes in _ACTION_PREFIXES.items():
            if lower.startswith(prefixes):
                when_text = _extract_move_target(message) if action == "move" else None
                return ReminderPlan(
                    is_reminder_request=True,
                    action=action,
                    query=context.last_title,
                    when_text=when_text,
                )

    return None


def _looks_reminder_related(message: str, *, context: ReminderConversationContext | None) -> bool:
    lower = message.lower()
    if any(token in lower for token in _REMINDER_KEYWORDS):
        return True
    if lower.startswith(("remind me", "nudge me", "remember to", "dont let me forget", "don't let me forget")):
        return True
    if context is None:
        return False
    if context.awaiting_time_title:
        return _looks_like_due_follow_up(lower)
    if context.last_title and any(reference in lower for reference in _PRONOUN_REFERENCES):
        return True
    return False


def _looks_like_due_follow_up(lower: str) -> bool:
    return any(
        token in lower
        for token in (
            "today",
            "tomorrow",
            "tonight",
            "morning",
            "afternoon",
            "evening",
            "next week",
            "next ",
            " in ",
            " at ",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            "/",
            "-",
            "am",
            "pm",
            "noon",
            "midnight",
            "lunch",
        )
    )


def _llm_plan_reminder_request(message: str, *, context: ReminderConversationContext | None) -> ReminderPlan:
    now = datetime.now().astimezone()
    system = (
        "You extract reminder tool arguments for Jarvin. "
        "Return JSON only with keys: "
        "is_reminder_request (boolean), action (string), title (string|null), query (string|null), "
        "when_text (string|null), due_at_iso (string|null), recurrence (string|null), window (string|null). "
        "Valid actions are create, list, list_routines, complete, delete, move, unknown. "
        "Supported recurrence values are once, daily, weekday, weekly, or null if not specified. "
        "Supported list windows are today, tomorrow, week, upcoming, or null. "
        "If the user is asking for a reminder but did not give enough timing information, set action=create and leave "
        "when_text and due_at_iso null. "
        "If you can confidently normalize natural time language into a precise local timestamp, set due_at_iso using ISO 8601 "
        "with timezone offset. Otherwise put a clean time phrase in when_text that Jarvin can parse, such as "
        "'tomorrow at 5pm', 'today at 1pm', or 'in 30 minutes'. "
        "For phrases like 'after lunch', choose a reasonable time around 1pm. "
        "For phrases like 'before my 3 PM meeting', choose roughly 30 minutes before if no better timing is available. "
        "If the user is referring to a prior reminder with words like 'it' or 'that', query may be null."
    )
    prompt = (
        f"Current local datetime: {now.isoformat()}\n"
        f"Recent reminder context:\n{_context_prompt(context)}\n\n"
        f"User message:\n{message}"
    )
    cfg_obj = build_jarvin_config(
        mode="agent_strong",
        system_instructions=system,
        temperature=0.1,
        max_tokens=260,
    )
    raw = generate_reply(prompt, cfg=cfg_obj, context=None)
    data = _parse_json_object(raw)
    return ReminderPlan(
        is_reminder_request=bool(data.get("is_reminder_request")),
        action=str(data.get("action") or "unknown").strip().lower(),
        title=_clean_text(data.get("title")),
        query=_clean_text(data.get("query")),
        when_text=_clean_text(data.get("when_text")),
        due_at_iso=_clean_text(data.get("due_at_iso")),
        recurrence=_clean_text(data.get("recurrence")),
        window=_normalize_window(data.get("window")),
    )


def _resolve_contextual_references(plan: ReminderPlan, *, context: ReminderConversationContext | None) -> ReminderPlan:
    if context is None:
        return plan

    query = plan.query
    if not query and plan.action in {"complete", "delete", "move"} and context.last_title:
        query = context.last_title

    title = plan.title
    recurrence = plan.recurrence
    if plan.action == "create" and not title and context.awaiting_time_title and (plan.when_text or plan.due_at_iso):
        title = context.awaiting_time_title
        recurrence = recurrence or context.awaiting_time_recurrence or "once"

    return ReminderPlan(
        is_reminder_request=plan.is_reminder_request,
        action=plan.action,
        title=title,
        query=query,
        when_text=plan.when_text,
        due_at_iso=plan.due_at_iso,
        recurrence=recurrence,
        window=plan.window,
    )


def _infer_window(lower: str) -> str:
    if "tomorrow" in lower:
        return "tomorrow"
    if "this week" in lower or "next 7 days" in lower or "next week" in lower:
        return "week"
    if "today" in lower:
        return "today"
    return "upcoming"


def _extract_move_target(message: str) -> str | None:
    match = re.search(r"\bto\s+(.+)$", message, re.IGNORECASE)
    if not match:
        return None
    return _clean_text(match.group(1))


def _context_prompt(context: ReminderConversationContext | None) -> str:
    if context is None:
        return "(none)"
    return (
        f"last_action={context.last_action}\n"
        f"last_title={context.last_title or ''}\n"
        f"awaiting_time_title={context.awaiting_time_title or ''}\n"
        f"awaiting_time_recurrence={context.awaiting_time_recurrence or ''}"
    )


def _normalize_window(value: object) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    lowered = cleaned.lower()
    if lowered in {"today", "tomorrow", "week", "upcoming"}:
        return lowered
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
