from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.ai_engine import build_jarvin_config, generate_reply
from backend.agent.chat.chat_organizer_context import (
    get_organizer_context,
    remember_organizer_context,
)
from backend.agent.chat.chat_organizer_pending_actions import (
    PendingOrganizerCleanupAction,
    set_pending_organizer_cleanup_action,
)
from backend.agent.reminders.reminder_request_planner import remember_reminder_context
from memory.calendar_events import list_calendar_occurrences
from memory.reminders import list_reminders

_OVERVIEW_HINTS = (
    "overview",
    "output all",
    "show all",
    "list all",
    "current events and reminders",
    "events and reminders",
    "quick overview",
)
_CLEANUP_HINTS = (
    "keep only",
    "everything else",
    "get rid of it",
    "get rid of everything else",
    "clean this up",
    "delete everything else",
    "remove everything else",
)
_DELETE_ALL_HINTS = (
    "delete all",
    "remove all",
    "cancel all",
    "delete everything",
    "remove everything",
    "all of them",
    "all of this",
    "delete it all",
    "remove it all",
    "clean slate",
    "start over",
    "wipe it all",
    "wipe them all",
    "get rid of it all",
    "get rid of them all",
)
_CALENDAR_HINTS = ("calendar", "event", "events", "appointment", "appointments", "meeting", "meetings")
_REMINDER_HINTS = ("reminder", "reminders", "task", "tasks", "to-do", "to-dos", "todo", "todos")


@dataclass(frozen=True)
class OrganizerReminderItem:
    reminder_id: int
    title: str
    due_at: str


@dataclass(frozen=True)
class OrganizerCalendarItem:
    event_id: int
    title: str
    starts_at: str
    location: str = ""


@dataclass(frozen=True)
class OrganizerSnapshot:
    reminders: tuple[OrganizerReminderItem, ...]
    calendar_events: tuple[OrganizerCalendarItem, ...]


@dataclass(frozen=True)
class OrganizerCleanupPlan:
    keep_reminder_ids: tuple[int, ...] = ()
    keep_calendar_event_ids: tuple[int, ...] = ()


def maybe_organizer_tool_response_impl(
    text: str,
    *,
    conversation_id,
    ToolChatResponse,
):
    message = str(text or "").strip()
    if not message:
        return None
    context = get_organizer_context(conversation_id)

    if _looks_like_cleanup_request(message, context=context):
        try:
            remember_organizer_context(conversation_id, action="cleanup")
            return ToolChatResponse(
                handled=True,
                reply=organizer_cleanup_reply(message, conversation_id=conversation_id),
                active_domain="organizer",
            )
        except Exception as exc:
            detail = str(exc).strip()
            fallback = "I couldn't clean up your current reminders and events just now."
            return ToolChatResponse(
                handled=True,
                reply=f"{fallback} {detail}".strip(),
                active_domain="organizer",
            )

    if _looks_like_combined_overview_request(message):
        try:
            remember_organizer_context(conversation_id, action="overview")
            return ToolChatResponse(
                handled=True,
                reply=combined_overview_reply(conversation_id=conversation_id),
                active_domain="organizer",
            )
        except Exception as exc:
            detail = str(exc).strip()
            fallback = "I couldn't pull together your current events and reminders just now."
            return ToolChatResponse(
                handled=True,
                reply=f"{fallback} {detail}".strip(),
                active_domain="organizer",
            )

    return None


def execute_organizer_action(
    action: str,
    *,
    text: str,
    conversation_id: int | None,
) -> str | None:
    normalized_action = str(action or "").strip().lower()
    if normalized_action == "overview":
        remember_organizer_context(conversation_id, action="overview")
        return combined_overview_reply(conversation_id=conversation_id)
    if normalized_action == "cleanup":
        remember_organizer_context(conversation_id, action="cleanup")
        return organizer_cleanup_reply(text, conversation_id=conversation_id)
    return None


def combined_overview_reply(*, conversation_id: int | None = None) -> str:
    snapshot = _build_snapshot()
    if snapshot.reminders:
        remember_reminder_context(
            conversation_id,
            action="list",
            last_title=snapshot.reminders[0].title,
            last_due_at=snapshot.reminders[0].due_at,
            last_listed_ids=[item.reminder_id for item in snapshot.reminders[:20]],
        )
    lines = ["Current overview:"]

    if snapshot.calendar_events:
        lines.append("")
        lines.append("Calendar events:")
        for event in snapshot.calendar_events:
            suffix = f" at {event.location}" if event.location else ""
            lines.append(f"- `{_format_display_time(event.starts_at)}` {event.title}{suffix}")
    else:
        lines.append("")
        lines.append("Calendar events:")
        lines.append("- `(none)`")

    if snapshot.reminders:
        lines.append("")
        lines.append("Reminders:")
        for reminder in snapshot.reminders:
            lines.append(f"- `{_format_display_time(reminder.due_at)}` {reminder.title}")
    else:
        lines.append("")
        lines.append("Reminders:")
        lines.append("- `(none)`")

    return "\n".join(lines)


def organizer_cleanup_reply(message: str, *, conversation_id: int | None) -> str:
    snapshot = _build_snapshot()
    if not snapshot.reminders and not snapshot.calendar_events:
        return "You do not have any current reminders or upcoming calendar events to clean up."

    delete_reminders, delete_calendar_events = _cleanup_scope(message)
    if _is_delete_all_request(message):
        keep_reminder_ids = (
            {item.reminder_id for item in snapshot.reminders}
            if not delete_reminders
            else set()
        )
        keep_calendar_event_ids = (
            {item.event_id for item in snapshot.calendar_events}
            if not delete_calendar_events
            else set()
        )
        return _stage_cleanup_plan(
            snapshot,
            conversation_id=conversation_id,
            keep_reminder_ids=keep_reminder_ids,
            keep_calendar_event_ids=keep_calendar_event_ids,
        )

    plan = _plan_cleanup(message, snapshot=snapshot)
    keep_reminder_ids = set(plan.keep_reminder_ids)
    keep_calendar_event_ids = set(plan.keep_calendar_event_ids)

    if not delete_reminders:
        keep_reminder_ids.update(item.reminder_id for item in snapshot.reminders)
    if not delete_calendar_events:
        keep_calendar_event_ids.update(item.event_id for item in snapshot.calendar_events)

    if not keep_reminder_ids and not keep_calendar_event_ids:
        raise ValueError("Tell me which reminder or calendar event you want to keep before I delete the rest.")

    return _stage_cleanup_plan(
        snapshot,
        conversation_id=conversation_id,
        keep_reminder_ids=keep_reminder_ids,
        keep_calendar_event_ids=keep_calendar_event_ids,
    )


def _plan_cleanup(message: str, *, snapshot: OrganizerSnapshot) -> OrganizerCleanupPlan:
    system = (
        "You choose which current Jarvin items to KEEP based on the user's cleanup request. "
        "Return JSON only with keys keep_reminder_ids and keep_calendar_event_ids. "
        "Each must be an array of integer ids from the provided current-item lists. "
        "Only keep items the user clearly wants to preserve. "
        "If the request is ambiguous, return empty arrays."
    )
    prompt = (
        "Current reminders:\n"
        f"{_render_reminder_candidates(snapshot.reminders)}\n\n"
        "Current calendar events:\n"
        f"{_render_calendar_candidates(snapshot.calendar_events)}\n\n"
        f"User cleanup request:\n{message}"
    )
    cfg_obj = build_jarvin_config(
        mode="agent_strong",
        system_instructions=system,
        temperature=0.1,
        max_tokens=220,
    )
    raw = generate_reply(prompt, cfg=cfg_obj, context=None)
    data = _parse_json_object(raw)
    reminder_ids = _coerce_ids(data.get("keep_reminder_ids"), valid_ids={item.reminder_id for item in snapshot.reminders})
    event_ids = _coerce_ids(data.get("keep_calendar_event_ids"), valid_ids={item.event_id for item in snapshot.calendar_events})
    return OrganizerCleanupPlan(
        keep_reminder_ids=tuple(reminder_ids),
        keep_calendar_event_ids=tuple(event_ids),
    )


def _build_snapshot() -> OrganizerSnapshot:
    local_now = datetime.now().astimezone()
    lower = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    upper = lower + timedelta(days=30)
    reminders = tuple(
        OrganizerReminderItem(
            reminder_id=int(item["id"]),
            title=str(item["title"]),
            due_at=str(item["due_at"]),
        )
        for item in list_reminders(status="pending", limit=50)
    )
    calendar_events = tuple(
        OrganizerCalendarItem(
            event_id=int(item["event_id"]),
            title=str(item["title"]),
            starts_at=str(item["starts_at"]),
            location=str(item.get("location") or ""),
        )
        for item in list_calendar_occurrences(lower=lower, upper=upper, limit=50)
    )
    return OrganizerSnapshot(reminders=reminders, calendar_events=calendar_events)


def _looks_like_combined_overview_request(message: str) -> bool:
    lower = message.lower()
    if not _has_any(lower, _OVERVIEW_HINTS):
        return False
    return _has_any(lower, _CALENDAR_HINTS) and _has_any(lower, _REMINDER_HINTS)


def _looks_like_cleanup_request(message: str, *, context) -> bool:
    lower = message.lower()
    if _has_any(lower, _CLEANUP_HINTS):
        return _has_any(lower, _REMINDER_HINTS) or _has_any(lower, _CALENDAR_HINTS) or context is not None
    if _has_any(lower, _DELETE_ALL_HINTS):
        return _has_any(lower, _REMINDER_HINTS) or _has_any(lower, _CALENDAR_HINTS) or context is not None
    return False


def _is_delete_all_request(message: str) -> bool:
    return _has_any(message.lower(), _DELETE_ALL_HINTS)


def _cleanup_scope(message: str) -> tuple[bool, bool]:
    lower = message.lower()
    mentions_reminders = _has_any(lower, _REMINDER_HINTS)
    mentions_calendar = _has_any(lower, _CALENDAR_HINTS)
    if mentions_reminders and not mentions_calendar:
        return True, False
    if mentions_calendar and not mentions_reminders:
        return False, True
    return True, True


def _render_reminder_candidates(items: tuple[OrganizerReminderItem, ...]) -> str:
    if not items:
        return "(none)"
    return "\n".join(
        f"- reminder_id={item.reminder_id} | due={_format_display_time(item.due_at)} | title={item.title}"
        for item in items
    )


def _render_calendar_candidates(items: tuple[OrganizerCalendarItem, ...]) -> str:
    if not items:
        return "(none)"
    return "\n".join(
        f"- event_id={item.event_id} | starts={_format_display_time(item.starts_at)} | title={item.title}"
        + (f" | location={item.location}" if item.location else "")
        for item in items
    )


def _keep_labels(
    snapshot: OrganizerSnapshot,
    *,
    keep_reminder_ids: set[int],
    keep_calendar_event_ids: set[int],
) -> list[str]:
    labels: list[str] = []
    for item in snapshot.reminders:
        if item.reminder_id in keep_reminder_ids:
            labels.append(f"Reminder `{item.title}` at `{_format_display_time(item.due_at)}`")
    for item in snapshot.calendar_events:
        if item.event_id in keep_calendar_event_ids:
            labels.append(f"Calendar event `{item.title}` at `{_format_display_time(item.starts_at)}`")
    return labels


def _stage_cleanup_plan(
    snapshot: OrganizerSnapshot,
    *,
    conversation_id: int | None,
    keep_reminder_ids: set[int],
    keep_calendar_event_ids: set[int],
) -> str:
    reminders_to_delete = [item for item in snapshot.reminders if item.reminder_id not in keep_reminder_ids]
    events_to_delete = [item for item in snapshot.calendar_events if item.event_id not in keep_calendar_event_ids]
    keep_labels = _keep_labels(
        snapshot,
        keep_reminder_ids=keep_reminder_ids,
        keep_calendar_event_ids=keep_calendar_event_ids,
    )
    delete_labels = _delete_labels(reminders_to_delete, events_to_delete)

    if not reminders_to_delete and not events_to_delete:
        return "There is nothing else to delete from that set."

    set_pending_organizer_cleanup_action(
        conversation_id,
        PendingOrganizerCleanupAction(
            reminder_ids=tuple(item.reminder_id for item in reminders_to_delete),
            calendar_event_ids=tuple(item.event_id for item in events_to_delete),
            keep_labels=tuple(keep_labels),
            delete_labels=tuple(delete_labels),
        ),
    )

    parts: list[str] = []
    if keep_labels:
        parts.append("I can keep these items:\n" + "\n".join(f"- {item}" for item in keep_labels))
    if delete_labels:
        parts.append("I can delete these items:\n" + "\n".join(f"- {item}" for item in delete_labels))
    parts.append("Reply `yes` to confirm, or `cancel` to leave everything as-is.")
    return "\n\n".join(parts)


def _delete_labels(
    reminders_to_delete: list[OrganizerReminderItem],
    events_to_delete: list[OrganizerCalendarItem],
) -> list[str]:
    labels: list[str] = []
    for item in reminders_to_delete:
        labels.append(f"Reminder `{item.title}` at `{_format_display_time(item.due_at)}`")
    for item in events_to_delete:
        labels.append(f"Calendar event `{item.title}` at `{_format_display_time(item.starts_at)}`")
    return labels


def _coerce_ids(value: object, *, valid_ids: set[int]) -> list[int]:
    if not isinstance(value, list):
        return []
    ids: list[int] = []
    for item in value:
        try:
            parsed = int(item)
        except (TypeError, ValueError):
            continue
        if parsed in valid_ids and parsed not in ids:
            ids.append(parsed)
    return ids


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


def _has_any(lower: str, hints: tuple[str, ...]) -> bool:
    return any(hint in lower for hint in hints)


def _format_display_time(value: str) -> str:
    raw = str(value or "").strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return parsed.astimezone().strftime("%Y-%m-%d %I:%M %p")
