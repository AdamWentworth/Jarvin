from __future__ import annotations

import json
import re
from dataclasses import dataclass

from backend.ai_engine import build_jarvin_config, generate_reply
from backend.agent.calendar.calendar_request_tools import CalendarPlan
from backend.agent.reminders.reminder_request_planner import ReminderPlan

_PERSONAL_ORG_KEYWORDS = (
    "reminder",
    "reminders",
    "task",
    "tasks",
    "calendar",
    "event",
    "events",
    "appointment",
    "appointments",
    "schedule",
    "meeting",
    "meetings",
)
_SHORT_FOLLOW_UP_HINTS = (
    "that",
    "it",
    "the one",
    "single reminder",
    "one and only",
    "yes",
    "9am",
    "9 a.m",
    "tomorrow",
)
_REMINDER_TARGET_CONFIRMATION_HINTS = (
    "the one and only",
    "one and only",
    "that is the one",
    "that's the one",
    "the one we have",
    "the only reminder",
)
_ACTIONABLE_REMINDER_CHANGE_HINTS = (
    "move",
    "reschedule",
    "delay",
    "postpone",
    "change",
    "update",
    "make sure",
    "set",
    " at ",
    " a.m",
    " am",
    " p.m",
    " pm",
    "noon",
    "midnight",
    "tomorrow",
    "today",
)
_ADDITIONAL_REMINDER_HINTS = ("as well", "also", "another reminder", "another one", "one more")
_REMINDER_CORRECTION_HINTS = ("i meant", "meant", "actually", "instead", "not right", "wrong", "should be")
_MULTI_ACTION_HINTS = (" and ", " then ", " plus ", " after that ")
_SUPPORTED_DOMAINS = {"organizer", "reminder", "calendar"}
_SUPPORTED_ACTIONS = {
    "organizer": {"overview", "cleanup"},
    "reminder": {"create", "move", "delete", "list", "confirm_target"},
    "calendar": {"create", "move", "delete", "lookup"},
}
_BLOCKING_REPLY_HINTS = (
    "reply `yes`",
    "reply `approve`",
    "what time should i",
    "tell me which",
    "tell me when",
    "please be more specific",
    "i found multiple matching",
)

@dataclass(frozen=True)
class PersonalOrganizationAction:
    domain: str
    action: str
    normalized_request: str | None = None
    title: str | None = None
    query: str | None = None
    when_text: str | None = None
    details: str | None = None
    window: str | None = None


@dataclass(frozen=True)
class PersonalOrganizationPlan:
    confidence: str
    actions: tuple[PersonalOrganizationAction, ...]
    reason: str | None = None

def maybe_plan_personal_organization_request(
    text: str,
    *,
    active_domain: str | None,
    reminder_context,
    calendar_context,
    organizer_context,
) -> PersonalOrganizationPlan | None:
    message = str(text or "").strip()
    if not message:
        return None

    if _looks_like_combined_overview(message):
        return PersonalOrganizationPlan(
            confidence="high",
            actions=(
                PersonalOrganizationAction(
                    domain="organizer",
                    action="overview",
                    normalized_request="show all my reminders and calendar events",
                ),
            ),
            reason="Combined overview request.",
        )

    if _looks_like_reminder_target_confirmation(
        message,
        active_domain=active_domain,
        reminder_context=reminder_context,
    ):
        return PersonalOrganizationPlan(
            confidence="high",
            actions=(
                PersonalOrganizationAction(
                    domain="reminder",
                    action="confirm_target",
                    query=_clean_text(getattr(reminder_context, "last_title", "")),
                ),
            ),
            reason="Reminder target confirmation.",
        )

    if _looks_like_contextual_additional_reminder_request(
        message,
        active_domain=active_domain,
        reminder_context=reminder_context,
    ):
        return PersonalOrganizationPlan(
            confidence="high",
            actions=(
                PersonalOrganizationAction(
                    domain="reminder",
                    action="create",
                    title=_clean_text(getattr(reminder_context, "last_title", "")),
                    when_text=message,
                ),
            ),
            reason="Additional reminder for the current item.",
        )

    if _looks_like_contextual_reminder_time_change(
        message,
        active_domain=active_domain,
        reminder_context=reminder_context,
    ):
        return PersonalOrganizationPlan(
            confidence="high",
            actions=(
                PersonalOrganizationAction(
                    domain="reminder",
                    action="move",
                    query=_clean_text(getattr(reminder_context, "last_title", "")),
                    when_text=message,
                ),
            ),
            reason="Reminder time follow-up.",
        )

    if not _looks_personal_organization_related(
        message,
        active_domain=active_domain,
        reminder_context=reminder_context,
        calendar_context=calendar_context,
        organizer_context=organizer_context,
    ):
        return None

    cfg_obj = build_jarvin_config(
        mode="agent_strong",
        system_instructions=_planner_system_prompt(),
        temperature=0.1,
        max_tokens=340,
    )
    prompt = (
        f"Current active follow-up domain: {active_domain or '(none)'}\n"
        f"Reminder context: {_context_summary(reminder_context, kind='reminder')}\n"
        f"Calendar context: {_context_summary(calendar_context, kind='calendar')}\n"
        f"Organizer context: {_context_summary(organizer_context, kind='organizer')}\n\n"
        f"User message:\n{message}"
    )
    raw = generate_reply(prompt, cfg=cfg_obj, context=None)
    data = _parse_json_object(raw)
    if not bool(data.get("is_personal_organization_request")):
        return None

    confidence = str(data.get("confidence") or "low").strip().lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"
    actions = _coerce_actions(data.get("actions"))
    if not actions:
        return None
    return PersonalOrganizationPlan(
        confidence=confidence,
        actions=actions,
        reason=_clean_text(data.get("reason")),
    )


def execute_personal_organization_plan(
    plan: PersonalOrganizationPlan,
    *,
    source_text: str,
    conversation_id,
    ToolChatResponse,
    execute_reminder_plan,
    execute_calendar_plan,
    execute_organizer_action,
):
    if not plan.actions or plan.confidence == "low":
        return None

    replies: list[str] = []
    active_domain: str | None = None
    for action in plan.actions:
        response = _execute_action(
            action,
            source_text=source_text,
            conversation_id=conversation_id,
            ToolChatResponse=ToolChatResponse,
            execute_reminder_plan=execute_reminder_plan,
            execute_calendar_plan=execute_calendar_plan,
            execute_organizer_action=execute_organizer_action,
        )
        if response is None or not response.handled or not response.reply:
            continue
        replies.append(response.reply.strip())
        active_domain = response.active_domain or action.domain
        if _is_blocking_response(response.reply):
            return ToolChatResponse(handled=True, reply="\n\n".join(replies), active_domain=active_domain)

    if not replies:
        return None
    return ToolChatResponse(handled=True, reply="\n\n".join(replies), active_domain=active_domain)


def _execute_action(
    action: PersonalOrganizationAction,
    *,
    source_text: str,
    conversation_id,
    ToolChatResponse,
    execute_reminder_plan,
    execute_calendar_plan,
    execute_organizer_action,
):
    if action.domain == "organizer":
        try:
            prompt = _action_prompt(action, source_text=source_text)
            reply = execute_organizer_action(
                action.action,
                text=prompt,
                conversation_id=conversation_id,
            )
        except Exception as exc:
            return _error_response(
                ToolChatResponse,
                active_domain="organizer",
                fallback="I couldn't work with your overview or cleanup request just now.",
                exc=exc,
            )
        if not reply:
            return None
        return ToolChatResponse(handled=True, reply=reply, active_domain="organizer")
    if action.domain == "reminder":
        if action.action == "confirm_target":
            title = _clean_text(action.query) or _clean_text(action.title) or "that reminder"
            return ToolChatResponse(
                handled=True,
                reply=f"I'm looking at reminder `{title}`. Tell me what you'd like to change or do with it.",
                active_domain="reminder",
            )
        try:
            reminder_plan = _build_reminder_plan(action)
            reply = execute_reminder_plan(reminder_plan, conversation_id=conversation_id)
        except Exception as exc:
            return _error_response(
                ToolChatResponse,
                active_domain="reminder",
                fallback="I couldn't manage that reminder just now.",
                exc=exc,
            )
        if not reply:
            return None
        return ToolChatResponse(handled=True, reply=reply, active_domain="reminder")
    if action.domain == "calendar":
        try:
            calendar_plan = _build_calendar_plan(action)
            raw_message = _action_prompt(action, source_text=source_text)
            reply = execute_calendar_plan(
                calendar_plan,
                raw_message=raw_message,
                conversation_id=conversation_id,
            )
        except Exception as exc:
            return _error_response(
                ToolChatResponse,
                active_domain="calendar",
                fallback="I couldn't work with your calendar just now.",
                exc=exc,
            )
        return ToolChatResponse(handled=True, reply=reply, active_domain="calendar")
    return None


def _build_reminder_plan(action: PersonalOrganizationAction) -> ReminderPlan:
    window = (_clean_text(action.window) or "").lower() or None
    return ReminderPlan(
        is_reminder_request=True,
        action=action.action,
        title=_clean_text(action.title),
        query=_clean_text(action.query),
        when_text=_clean_text(action.when_text),
        due_at_iso=None,
        recurrence=None,
        window=window,
    )


def _build_calendar_plan(action: PersonalOrganizationAction) -> CalendarPlan:
    return CalendarPlan(
        is_calendar_request=True,
        action=action.action,
        query=_clean_text(action.query) or _clean_text(action.details),
        when_text=_clean_text(action.when_text),
        new_title=_clean_text(action.title),
        new_location=None,
        new_description=None,
        window_days=None,
    )


def _action_prompt(action: PersonalOrganizationAction, *, source_text: str) -> str:
    normalized = _clean_text(action.normalized_request)
    if normalized:
        return normalized
    if action.domain == "organizer":
        if action.action == "overview":
            return "show all my reminders and calendar events"
        return _clean_text(action.details) or source_text
    if action.domain == "reminder":
        if action.action == "list":
            window = (_clean_text(action.window) or "").lower()
            if window == "today":
                return "show me my reminders for today"
            if window == "tomorrow":
                return "show me my reminders for tomorrow"
            if window == "week":
                return "show me my reminders for this week"
            return "show me my reminders"
        if action.action == "create":
            title = _clean_text(action.title) or _clean_text(action.query) or "that"
            when_text = _clean_text(action.when_text)
            return f"remind me to {title} {when_text}".strip()
        if action.action == "move":
            query = _clean_text(action.query) or _clean_text(action.title) or "that reminder"
            when_text = _clean_text(action.when_text) or "later"
            return f"move reminder {query} to {when_text}".strip()
        if action.action == "delete":
            query = _clean_text(action.query) or _clean_text(action.title) or "that reminder"
            return f"delete reminder {query}"
    if action.domain == "calendar":
        if action.action == "lookup":
            window = (_clean_text(action.window) or "").lower()
            if window == "today":
                return "what's on my calendar today"
            if window == "tomorrow":
                return "what's on my calendar tomorrow"
            if window == "week":
                return "what's on my calendar this week"
            return "what's on my calendar"
        if action.action == "create":
            details = _clean_text(action.details) or _clean_text(action.query) or ""
            return f"put {details} on my calendar".strip()
        if action.action == "move":
            query = _clean_text(action.query) or "that event"
            when_text = _clean_text(action.when_text) or "later"
            return f"move {query} to {when_text}".strip()
        if action.action == "delete":
            query = _clean_text(action.query) or "that event"
            return f"delete calendar event {query}"
    return source_text


def _looks_personal_organization_related(
    message: str,
    *,
    active_domain: str | None,
    reminder_context,
    calendar_context,
    organizer_context,
) -> bool:
    lower = message.lower()
    if any(token in lower for token in _PERSONAL_ORG_KEYWORDS):
        return True
    if active_domain in {"organizer", "reminder", "calendar"} and any(token in lower for token in _SHORT_FOLLOW_UP_HINTS):
        return True
    if reminder_context and any(token in lower for token in _SHORT_FOLLOW_UP_HINTS):
        return True
    if calendar_context and any(token in lower for token in ("that", "it", "tomorrow", "today")):
        return True
    return organizer_context is not None and any(token in lower for token in _SHORT_FOLLOW_UP_HINTS)


def _looks_like_reminder_target_confirmation(
    message: str,
    *,
    active_domain: str | None,
    reminder_context,
) -> bool:
    if reminder_context is None:
        return False
    if active_domain not in {None, "reminder", "organizer"}:
        return False
    lower = message.lower()
    if any(hint in lower for hint in _ACTIONABLE_REMINDER_CHANGE_HINTS):
        return False
    return any(hint in lower for hint in _REMINDER_TARGET_CONFIRMATION_HINTS)


def _looks_like_contextual_additional_reminder_request(
    message: str,
    *,
    active_domain: str | None,
    reminder_context,
) -> bool:
    if reminder_context is None or active_domain not in {None, "reminder", "organizer"}:
        return False
    lower = message.lower()
    if _looks_like_multi_action_request(lower):
        return False
    return _looks_like_due_follow_up(lower) and any(hint in lower for hint in _ADDITIONAL_REMINDER_HINTS)


def _looks_like_contextual_reminder_time_change(
    message: str,
    *,
    active_domain: str | None,
    reminder_context,
) -> bool:
    if reminder_context is None or active_domain not in {None, "reminder", "organizer"}:
        return False
    lower = message.lower()
    if _looks_like_multi_action_request(lower):
        return False
    if not _looks_like_due_follow_up(lower):
        return False
    if any(hint in lower for hint in _ADDITIONAL_REMINDER_HINTS):
        return False
    return any(hint in lower for hint in _ACTIONABLE_REMINDER_CHANGE_HINTS) or any(
        hint in lower for hint in _REMINDER_CORRECTION_HINTS
    )


def _looks_like_due_follow_up(lower: str) -> bool:
    return any(
        token in lower
        for token in ("today", "tomorrow", "next ", " at ", " a.m", " am", " p.m", " pm", "noon", "midnight", "morning", "afternoon", "evening")
    )


def _looks_like_multi_action_request(lower: str) -> bool:
    if not any(token in lower for token in _MULTI_ACTION_HINTS):
        return False
    has_delete = any(token in lower for token in ("delete", "remove", "cancel"))
    has_add_or_change = any(token in lower for token in ("remind me", "add", "create", "move", "change", "update"))
    return has_delete and has_add_or_change


def _looks_like_combined_overview(message: str) -> bool:
    lower = message.lower()
    overview_hint = any(token in lower for token in ("show", "list", "output", "overview", "current"))
    return overview_hint and "reminder" in lower and any(token in lower for token in ("event", "calendar", "appointment"))


def _planner_system_prompt() -> str:
    return (
        "You plan Jarvin personal organization actions for reminders, calendar, and organizer overviews. "
        "Return JSON only with keys: is_personal_organization_request, confidence, reason, actions. "
        "Each action must include: domain, action, normalized_request, title, query, when_text, details, window. "
        "Supported domains: organizer, reminder, calendar. "
        "Supported organizer actions: overview, cleanup. "
        "Supported reminder actions: create, move, delete, list, confirm_target. "
        "Supported calendar actions: create, move, delete, lookup. "
        "Use multiple actions when the user asks for multiple separate reminder/calendar operations. "
        "For reminder time edits, prefer action=move, not create. "
        "For follow-ups like 'remind me as well at 10am' about the currently selected reminder, use action=create with the existing reminder title. "
        "If the user confirms a previously identified reminder with language like 'yes that is the one' or refers to a single reminder, "
        "use action=confirm_target when they are only confirming the target, or action=move when they also include the new time. "
        "For combined reminders-plus-events overview requests, use a single organizer overview action. "
        "normalized_request should be a concise imperative instruction for the domain executor, like "
        "'move reminder Go to Costco to tomorrow at 9am' or 'show all my reminders and calendar events'. "
        "If the message is not about reminders, calendar, or organizer overviews/cleanup, return is_personal_organization_request=false. "
        "Do not answer the user."
    )


def _coerce_actions(value: object) -> tuple[PersonalOrganizationAction, ...]:
    if not isinstance(value, list):
        return ()
    actions: list[PersonalOrganizationAction] = []
    for item in value[:4]:
        if not isinstance(item, dict):
            continue
        domain = str(item.get("domain") or "").strip().lower()
        action = str(item.get("action") or "").strip().lower()
        if domain not in _SUPPORTED_DOMAINS or action not in _SUPPORTED_ACTIONS[domain]:
            continue
        actions.append(
            PersonalOrganizationAction(
                domain=domain,
                action=action,
                normalized_request=_clean_text(item.get("normalized_request")),
                title=_clean_text(item.get("title")),
                query=_clean_text(item.get("query")),
                when_text=_clean_text(item.get("when_text")),
                details=_clean_text(item.get("details")),
                window=_clean_text(item.get("window")),
            )
        )
    return tuple(actions)


def _context_summary(context, *, kind: str) -> str:
    if context is None:
        return "(none)"
    if kind == "reminder":
        return (
            f"last_action={getattr(context, 'last_action', '')}; "
            f"last_title={getattr(context, 'last_title', '')}; "
            f"last_listed_ids={len(getattr(context, 'last_listed_ids', ()) or ())}"
        )
    if kind == "calendar":
        return (
            f"last_action={getattr(context, 'last_action', '')}; "
            f"last_query={getattr(context, 'last_query', '')}"
        )
    return f"last_action={getattr(context, 'last_action', '')}"


def _parse_json_object(text: str) -> dict[str, object]:
    body = str(text or "").strip()
    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", body, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}


def _clean_text(value: object) -> str | None:
    cleaned = str(value or "").strip()
    return cleaned or None


def _error_response(ToolChatResponse, *, active_domain: str, fallback: str, exc: Exception):
    detail = str(exc).strip()
    reply = f"{fallback} {detail}".strip() if detail else fallback
    return ToolChatResponse(handled=True, reply=reply, active_domain=active_domain)


def _is_blocking_response(reply: str) -> bool:
    lower = str(reply or "").strip().lower()
    return any(hint in lower for hint in _BLOCKING_REPLY_HINTS)
