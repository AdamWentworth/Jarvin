from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re

from backend.agent.reminders.reminder_request_planner import (
    clear_reminder_context,
    get_reminder_context,
    maybe_plan_reminder_request,
    remember_reminder_context,
)
from backend.agent.reminders.reminder_datetime_utils import (
    display_due,
    parse_iso,
    parse_due_text,
    parse_recurring_schedule,
)
from memory.reminders import (
    advance_due_at,
    complete_reminder,
    create_reminder,
    delete_reminder,
    find_reminders,
    get_reminder,
    list_due_reminders,
    list_reminders,
    update_reminder,
)

_REMIND_ME_RE = re.compile(
    r"^(?:please\s+)?(?:remind me to|add (?:a )?reminder to|set (?:a )?reminder to)\s+(?P<body>.+)$",
    re.IGNORECASE,
)
_ROUTINE_PREFIX_RE = re.compile(
    r"^(?:please\s+)?(?P<schedule>(?:every day|each day|daily|every weekday|each weekday|weekly|every week(?:\s+on)?\s+\w+))(?:\s+at\s+(?P<time>[^,]+?))?\s+remind me to\s+(?P<title>.+)$",
    re.IGNORECASE,
)
_ROUTINE_SUFFIX_RE = re.compile(
    r"^(?P<title>.+?)\s+(?P<schedule>(?:every day|each day|daily|every weekday|each weekday|weekly|every week(?:\s+on)?\s+\w+))(?:\s+at\s+(?P<time>.+))?$",
    re.IGNORECASE,
)
_RELATIVE_RE = re.compile(r"\bin\s+(?P<count>\d+)\s+(?P<unit>minutes?|hours?|days?)\b", re.IGNORECASE)
_TRAILING_SCHEDULE_RE = re.compile(
    r"^(?P<title>.+?)\s+(?P<when>(?:in\s+\d+\s+(?:minutes?|hours?|days?)|today|tomorrow|tonight|this morning|this afternoon|this evening|next week|next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?)(?:\s+at\s+.+)?)$",
    re.IGNORECASE,
)
_TIME_ONLY_RE = re.compile(r"^(?P<title>.+?)\s+(?P<when>at\s+.+)$", re.IGNORECASE)
_LIST_RE = re.compile(
    r"(?:what(?:'s| is)\s+(?:on\s+)?my\s+(?:reminders|tasks|to-?dos)|show\s+(?:me\s+)?my\s+(?:reminders|tasks|to-?dos)|list\s+(?:my\s+)?(?:reminders|tasks|to-?dos)|what do i need to do(?:\s+(?:today|tomorrow|this week))?)",
    re.IGNORECASE,
)
_LIST_ROUTINES_RE = re.compile(r"(?:what(?:'s| is)\s+my\s+(?:routine|routines)|show\s+(?:me\s+)?my\s+routines?)", re.IGNORECASE)
_COMPLETE_RE = re.compile(
    r"^(?:please\s+)?(?:mark|complete|finish)\s+(?P<query>.+?)\s+(?:done|complete)$",
    re.IGNORECASE,
)
_DELETE_RE = re.compile(
    r"^(?:please\s+)?(?:delete|remove|cancel)\s+(?:the\s+)?(?:reminder|reminders|task|tasks|to-?do|to-?dos)\s+(?P<query>.+)$",
    re.IGNORECASE,
)
_DELETE_RECENT_LIST_RE = re.compile(
    r"^(?:please\s+)?(?:delete|remove|cancel)\s+(?P<query>(?:the\s+)?(?:two|2|both|all|those|these|all of them|all of those)\s+(?:reminders|tasks|to-?dos))$",
    re.IGNORECASE,
)
_MOVE_RE = re.compile(
    r"^(?:please\s+)?(?:move|reschedule|delay|postpone)\s+(?:the\s+)?(?:reminder|task|to-?do)\s+(?P<query>.+?)\s+to\s+(?P<when>.+)$",
    re.IGNORECASE,
)
_RECENT_LIST_BULK_RE = re.compile(
    r"\b(?:both|all|those|these|the two|the 2|two reminders|2 reminders|two tasks|2 tasks|all of them|all of those|those reminders|these reminders)\b",
    re.IGNORECASE,
)
_TIME_ONLY_UPDATE_RE = re.compile(
    r"^(?:at\s+)?(?:\d{1,2}(?::\d{2})?\s*(?:am|pm)?|noon|midnight|morning|afternoon|evening|tonight|lunch)$",
    re.IGNORECASE,
)
_CONTEXTUAL_DUE_EXTRACT_RE = re.compile(
    r"(?P<when>(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)(?:\s+(?:today|tomorrow|tonight))?|"
    r"(?:today|tomorrow|tonight)\s+at\s+\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)|"
    r"(?:today|tomorrow|tonight|next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+(?:morning|afternoon|evening)|"
    r"(?:morning|afternoon|evening|noon|midnight|lunch)(?:\s+tomorrow)?)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ReminderDraft:
    title: str
    due_at: datetime
    recurrence: str = "once"


def maybe_handle_reminder_request(text: str, *, conversation_id: int | None = None) -> str | None:
    message = (text or "").strip()
    if not message:
        return None

    try:
        if _should_try_planner_first(message, conversation_id=conversation_id):
            planner_reply = _maybe_execute_planned_reminder(message, conversation_id=conversation_id)
            if planner_reply is not None:
                return planner_reply

        if _LIST_ROUTINES_RE.search(message):
            return _list_reply(routines_only=True, window="upcoming", conversation_id=conversation_id)

        if _LIST_RE.search(message):
            return _list_reply(
                routines_only=False,
                window=_infer_list_window(message),
                conversation_id=conversation_id,
            )

        complete_match = _COMPLETE_RE.search(message)
        if complete_match:
            return _complete_reply(_clean_text(complete_match.group("query")), conversation_id=conversation_id)

        bulk_delete_match = _DELETE_RECENT_LIST_RE.search(message)
        if bulk_delete_match:
            return _delete_reply(_clean_text(bulk_delete_match.group("query")), conversation_id=conversation_id)

        delete_match = _DELETE_RE.search(message)
        if delete_match:
            return _delete_reply(_clean_text(delete_match.group("query")), conversation_id=conversation_id)

        move_match = _MOVE_RE.search(message)
        if move_match:
            return _move_reply(
                _clean_text(move_match.group("query")),
                _clean_text(move_match.group("when")),
                conversation_id=conversation_id,
            )

        legacy_error: ValueError | None = None
        try:
            draft = _parse_reminder_draft(message)
        except ValueError as exc:
            draft = None
            legacy_error = exc
        if draft is None:
            planner_reply = _maybe_execute_planned_reminder(message, conversation_id=conversation_id)
            if planner_reply is not None:
                return planner_reply
            if legacy_error is not None:
                return str(legacy_error)
            return None

        created = create_reminder(draft.title, due_at=draft.due_at, recurrence=draft.recurrence)
        remember_reminder_context(
            conversation_id,
            action="create",
            last_title=str(created["title"]),
            last_due_at=str(created["due_at"]),
            last_listed_ids=[int(created["id"])],
        )
        recurrence_note = (
            f" This will repeat `{created['recurrence']}`."
            if created["recurrence"] != "once"
            else ""
        )
        return f"Saved reminder `{created['title']}` for `{display_due(created['due_at'])}`.{recurrence_note}"
    except ValueError as exc:
        return str(exc)


def _should_try_planner_first(message: str, *, conversation_id: int | None) -> bool:
    lower = message.lower()
    if get_reminder_context(conversation_id) is not None:
        return True
    return any(
        token in lower
        for token in (
            "nudge me",
            "don't let me forget",
            "dont let me forget",
            "remember to",
            "make sure i remember",
            "after lunch",
            "before ",
            "note to self",
        )
    )


def _maybe_execute_planned_reminder(message: str, *, conversation_id: int | None) -> str | None:
    plan = maybe_plan_reminder_request(message, conversation_id=conversation_id)
    if plan is None or plan.action == "unknown":
        return None
    return execute_reminder_plan(plan, conversation_id=conversation_id)


def handle_reminder_command(rest: str) -> str:
    body = str(rest or "").strip()
    if not body or body.lower() in {"help", "list"}:
        return _list_reply(routines_only=False, window="upcoming")

    lower = body.lower()
    if lower.startswith("list routines"):
        return _list_reply(routines_only=True, window="upcoming")
    if lower.startswith("add "):
        text = body[4:].strip()
        draft = _parse_reminder_draft(f"remind me to {text}")
        if draft is None:
            raise ValueError("Use `/tool reminder add <task> tomorrow at 9am` or `/tool reminder add every weekday at 8am remind me to stretch`.")
        created = create_reminder(draft.title, due_at=draft.due_at, recurrence=draft.recurrence)
        return f"Saved reminder `{created['title']}` for `{display_due(created['due_at'])}`."
    if lower.startswith("done "):
        return _complete_reply(body[5:].strip())
    if lower.startswith("delete "):
        return _delete_reply(body[7:].strip())
    if lower.startswith("move "):
        query, sep, when_text = body[5:].partition("|")
        if not sep:
            raise ValueError("Use `/tool reminder move <reminder name> | <new date/time>`.")
        return _move_reply(_clean_text(query), _clean_text(when_text))
    raise ValueError("Use `/tool reminder list`, `/tool reminder add ...`, `/tool reminder done ...`, or `/tool reminder move ...`.")


def _parse_reminder_draft(message: str) -> ReminderDraft | None:
    recurring_prefix = _ROUTINE_PREFIX_RE.match(message)
    if recurring_prefix:
        schedule = recurring_prefix.group("schedule")
        time_hint = recurring_prefix.group("time")
        title = _clean_text(recurring_prefix.group("title"))
        recurrence, due_at = parse_recurring_schedule(schedule, time_hint=time_hint)
        return ReminderDraft(title=title, due_at=due_at, recurrence=recurrence)

    remind_match = _REMIND_ME_RE.match(message)
    if not remind_match:
        return None

    body = remind_match.group("body").strip()
    recurring_suffix = _ROUTINE_SUFFIX_RE.match(body)
    if recurring_suffix:
        title = _clean_text(recurring_suffix.group("title"))
        recurrence, due_at = parse_recurring_schedule(
            recurring_suffix.group("schedule"),
            time_hint=recurring_suffix.group("time"),
        )
        return ReminderDraft(title=title, due_at=due_at, recurrence=recurrence)

    relative_match = _RELATIVE_RE.search(body)
    if relative_match:
        title = _clean_text(body[: relative_match.start()])
        due_at = parse_due_text(relative_match.group(0))
        return ReminderDraft(title=title, due_at=due_at, recurrence="once")

    trailing_match = _TRAILING_SCHEDULE_RE.match(body)
    if trailing_match:
        title = _clean_text(trailing_match.group("title"))
        due_at = parse_due_text(trailing_match.group("when"))
        return ReminderDraft(title=title, due_at=due_at, recurrence="once")

    time_only_match = _TIME_ONLY_RE.match(body)
    if time_only_match:
        title = _clean_text(time_only_match.group("title"))
        due_at = parse_due_text(time_only_match.group("when"))
        return ReminderDraft(title=title, due_at=due_at, recurrence="once")

    raise ValueError(
        "I can save that reminder once you give me a time, like `remind me to call mom tomorrow at 5pm` "
        "or `remind me to stretch in 30 minutes`."
    )


def execute_reminder_plan(plan, *, conversation_id: int | None) -> str:
    action = str(plan.action or "").strip().lower()
    if action == "update":
        action = "move"
    if action == "list_routines":
        return _list_reply(routines_only=True, window=plan.window or "upcoming", conversation_id=conversation_id)
    if action == "list":
        return _list_reply(routines_only=False, window=plan.window or "upcoming", conversation_id=conversation_id)
    if action == "complete":
        query = _resolve_query_text(plan.query, conversation_id=conversation_id)
        if not query:
            raise ValueError("Tell me which reminder to mark done.")
        return _complete_reply(query, conversation_id=conversation_id)
    if action == "delete":
        query = _resolve_query_text(plan.query, conversation_id=conversation_id)
        if not query:
            raise ValueError("Tell me which reminder to delete.")
        return _delete_reply(query, conversation_id=conversation_id)
    if action == "move":
        query = _resolve_query_text(plan.query or plan.title, conversation_id=conversation_id)
        if not query:
            raise ValueError("Tell me which reminder to move.")
        when_text = _normalize_contextual_when_text(plan.when_text or plan.due_at_iso or "")
        if not when_text:
            raise ValueError("Tell me when you want that reminder moved to.")
        return _move_reply(query, when_text, conversation_id=conversation_id)
    if action == "create":
        title = _clean_text(plan.title or "")
        recurrence = _normalize_planner_recurrence(plan.recurrence)
        due_at = _coerce_plan_due(plan, conversation_id=conversation_id, title=title)
        if not title:
            raise ValueError("Tell me what you want me to remind you about.")
        if due_at is None:
            remember_reminder_context(
                conversation_id,
                action="awaiting_time",
                last_title=title,
                awaiting_time_title=title,
                awaiting_time_recurrence=recurrence,
            )
            return (
                f"What time should I set reminder `{title}` for? "
                "You can say something like `tomorrow at 5pm` or `in 30 minutes`."
            )
        created = create_reminder(title, due_at=due_at, recurrence=recurrence)
        remember_reminder_context(
            conversation_id,
            action="create",
            last_title=str(created["title"]),
            last_due_at=str(created["due_at"]),
            last_listed_ids=[int(created["id"])],
        )
        recurrence_note = (
            f" This will repeat `{created['recurrence']}`."
            if created["recurrence"] != "once"
            else ""
        )
        return f"Saved reminder `{created['title']}` for `{display_due(created['due_at'])}`.{recurrence_note}"
    return None


def _list_reply(*, routines_only: bool, window: str, conversation_id: int | None = None) -> str:
    if routines_only:
        reminders = list_reminders(status="pending", recurrence="daily", limit=100) + list_reminders(
            status="pending",
            recurrence="weekday",
            limit=100,
        ) + list_reminders(status="pending", recurrence="weekly", limit=100)
        reminders = sorted(reminders, key=lambda item: item["due_at"])
        if not reminders:
            return "You do not have any active routines yet."
        remember_reminder_context(
            conversation_id,
            action="list_routines",
            last_title=str(reminders[0]["title"]),
            last_due_at=str(reminders[0]["due_at"]),
            last_listed_ids=[int(item["id"]) for item in reminders[:20]],
        )
        lines = [
            f"- `{item['title']}` at `{display_due(item['due_at'])}` (`{item['recurrence']}`)"
            for item in reminders[:20]
        ]
        return "Active routines:\n" + "\n".join(lines)

    if window == "today":
        end = datetime.now().astimezone().replace(hour=23, minute=59, second=59, microsecond=0)
        reminders = [
            item for item in list_due_reminders(minutes_ahead=int((end - datetime.now().astimezone()).total_seconds() // 60), limit=50)
        ]
        label = "today"
    elif window == "tomorrow":
        now = datetime.now().astimezone()
        end = (now + timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=0)
        reminders = [
            item for item in list_reminders(status="pending", limit=100)
            if parse_iso(item["due_at"]).date() == (now.date() + timedelta(days=1))
        ]
        label = "tomorrow"
    elif window == "week":
        now = datetime.now().astimezone()
        upper = now + timedelta(days=7)
        reminders = [
            item for item in list_reminders(status="pending", limit=100)
            if parse_iso(item["due_at"]) <= upper
        ]
        label = "the next 7 days"
    else:
        reminders = list_reminders(status="pending", limit=20)
        label = "upcoming"

    if not reminders:
        return f"You do not have any pending reminders for {label}."

    remember_reminder_context(
        conversation_id,
        action="list",
        last_title=str(reminders[0]["title"]),
        last_due_at=str(reminders[0]["due_at"]),
        last_listed_ids=[int(item["id"]) for item in reminders[:20]],
    )
    lines = []
    for item in reminders[:20]:
        recurrence = f" ({item['recurrence']})" if item["recurrence"] != "once" else ""
        overdue = " [overdue]" if item["is_overdue"] else ""
        lines.append(f"- `{display_due(item['due_at'])}` {item['title']}{recurrence}{overdue}")
    return f"Pending reminders for {label}:\n" + "\n".join(lines)


def _complete_reply(query: str, *, conversation_id: int | None = None) -> str:
    matches = _find_contextual_matches(query, conversation_id=conversation_id, include_done=False, limit=5)
    reminder = _pick_single_match(matches, query)
    updated = complete_reminder(int(reminder["id"]))
    remember_reminder_context(
        conversation_id,
        action="complete",
        last_title=str(updated["title"]),
        last_due_at=str(updated["due_at"]),
        last_listed_ids=[int(updated["id"])],
    )
    if updated["recurrence"] == "once":
        return f"Marked `{updated['title']}` as done."
    return (
        f"Completed `{updated['title']}` for now. "
        f"The next `{updated['recurrence']}` reminder is set for `{display_due(updated['due_at'])}`."
    )


def _delete_reply(query: str, *, conversation_id: int | None = None) -> str:
    bulk_matches = _recent_list_bulk_matches(query, conversation_id=conversation_id, include_done=True)
    if bulk_matches is not None:
        deleted = [delete_reminder(int(item["id"])) for item in bulk_matches]
        clear_reminder_context(conversation_id)
        if len(deleted) == 1:
            return f"Deleted reminder `{deleted[0]['title']}`."
        titles = ", ".join(f"`{item['title']}`" for item in deleted)
        return f"Deleted {len(deleted)} reminders: {titles}."

    matches = _find_contextual_matches(query, conversation_id=conversation_id, include_done=True, limit=5)
    reminder = _pick_single_match(matches, query)
    deleted = delete_reminder(int(reminder["id"]))
    clear_reminder_context(conversation_id)
    return f"Deleted reminder `{deleted['title']}`."


def _move_reply(query: str, when_text: str, *, conversation_id: int | None = None) -> str:
    matches = _find_contextual_matches(query, conversation_id=conversation_id, include_done=False, limit=5)
    reminder = _pick_single_match(matches, query)
    due_at = _coerce_move_due(reminder, when_text)
    updated = update_reminder(int(reminder["id"]), due_at=due_at)
    if updated["recurrence"] != "once":
        advanced = advance_due_at(updated["due_at"], updated["recurrence"], now=datetime.now().astimezone() - timedelta(seconds=1))
        updated = update_reminder(int(reminder["id"]), due_at=advanced)
    remember_reminder_context(
        conversation_id,
        action="move",
        last_title=str(updated["title"]),
        last_due_at=str(updated["due_at"]),
        last_listed_ids=[int(updated["id"])],
    )
    return f"Moved `{updated['title']}` to `{display_due(updated['due_at'])}`."


def _coerce_move_due(reminder: dict[str, object], when_text: str) -> datetime:
    due_at = parse_due_text(when_text)
    if _has_date_hint(when_text):
        return due_at
    existing_due = parse_iso(str(reminder["due_at"]))
    local_tz = existing_due.tzinfo or datetime.now().astimezone().tzinfo
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=local_tz)
    if existing_due.tzinfo is None:
        existing_due = existing_due.replace(tzinfo=local_tz)
    return existing_due.astimezone().replace(
        hour=due_at.hour,
        minute=due_at.minute,
        second=0,
        microsecond=0,
    )


def _resolve_query_text(query: str | None, *, conversation_id: int | None) -> str:
    cleaned = _clean_text(query or "")
    if cleaned:
        return cleaned
    context = get_reminder_context(conversation_id)
    if context and context.last_title:
        return context.last_title
    return ""


def _normalize_planner_recurrence(value: str | None) -> str:
    if value is None:
        return "once"
    lowered = _clean_text(value or "")
    if not lowered:
        return "once"
    lowered = lowered.lower()
    if lowered in {"once", "daily", "weekday", "weekly"}:
        return lowered
    raise ValueError(
        "I can handle one-time, daily, weekday, or weekly reminders right now. "
        f"I don't support `{lowered}` reminders yet."
    )
def _coerce_plan_due(plan, *, conversation_id: int | None, title: str) -> datetime | None:
    local_tz = datetime.now().astimezone().tzinfo
    when_text = _normalize_contextual_when_text(plan.when_text or "")
    parsed_when = parse_due_text(when_text) if when_text else None
    if parsed_when is not None and parsed_when.tzinfo is None:
        parsed_when = parsed_when.replace(tzinfo=local_tz)
    due_at_iso = _clean_text(plan.due_at_iso or "")
    if due_at_iso:
        normalized = due_at_iso.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=local_tz)
        parsed = parsed.astimezone()
        if parsed_when is None:
            return parsed
        if abs((parsed - parsed_when).total_seconds()) <= 5400:
            return parsed
        return parsed_when
    context = get_reminder_context(conversation_id)
    if (
        parsed_when is not None
        and context is not None
        and context.last_due_at
        and context.last_title
        and title
        and title.strip().lower() == str(context.last_title).strip().lower()
        and not _has_date_hint(when_text)
    ):
        return _coerce_due_against_existing_date(context.last_due_at, parsed_when)
    return parsed_when


def _coerce_due_against_existing_date(existing_due_at: str, parsed_when: datetime) -> datetime:
    existing_due = parse_iso(existing_due_at)
    local_tz = existing_due.tzinfo or datetime.now().astimezone().tzinfo
    if parsed_when.tzinfo is None:
        parsed_when = parsed_when.replace(tzinfo=local_tz)
    if existing_due.tzinfo is None:
        existing_due = existing_due.replace(tzinfo=local_tz)
    return existing_due.astimezone().replace(
        hour=parsed_when.hour,
        minute=parsed_when.minute,
        second=0,
        microsecond=0,
    )


def _normalize_contextual_when_text(value: str) -> str:
    cleaned = _clean_text(value or "")
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    for marker in ("i meant ", "meant ", "actually ", "instead "):
        index = lowered.rfind(marker)
        if index >= 0:
            candidate = _clean_text(cleaned[index + len(marker):])
            if candidate:
                return candidate
    matches = [match.group("when") for match in _CONTEXTUAL_DUE_EXTRACT_RE.finditer(cleaned)]
    if matches:
        return _clean_text(matches[-1])
    return cleaned


def _has_date_hint(when_text: str) -> bool:
    lower = _clean_text(when_text or "").lower()
    if not lower:
        return False
    if _TIME_ONLY_UPDATE_RE.fullmatch(lower):
        return False
    if re.search(r"\bin\s+\d+\s+(?:minutes?|hours?|days?)\b", lower):
        return True
    if re.search(r"\b(?:today|tomorrow|next week|next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", lower):
        return True
    if re.search(r"\b\d{4}-\d{2}-\d{2}\b", lower) or re.search(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", lower):
        return True
    return False
def _pick_single_match(matches: list[dict[str, object]], query: str) -> dict[str, object]:
    if not matches:
        raise ValueError(f"I couldn't find a reminder matching '{query}'.")
    if len(matches) > 1:
        lines = [f"- `{item['title']}` due `{display_due(str(item['due_at']))}`" for item in matches[:5]]
        raise ValueError("I found multiple matching reminders. Please be more specific:\n" + "\n".join(lines))
    return matches[0]


def _find_contextual_matches(
    query: str,
    *,
    conversation_id: int | None,
    include_done: bool,
    limit: int,
) -> list[dict[str, object]]:
    contextual = _contextual_single_match(query, conversation_id=conversation_id, include_done=include_done)
    if contextual is not None:
        return contextual
    return find_reminders(query, include_done=include_done, limit=limit)


def _contextual_single_match(
    query: str,
    *,
    conversation_id: int | None,
    include_done: bool,
) -> list[dict[str, object]] | None:
    context = get_reminder_context(conversation_id)
    if context is None:
        return None
    lowered = _clean_text(query or "").lower()
    if not lowered:
        return None
    if not _looks_like_contextual_reminder_reference(lowered, context_last_title=context.last_title):
        return None
    if len(context.last_listed_ids) == 1:
        try:
            reminder = get_reminder(int(context.last_listed_ids[0]))
        except ValueError:
            reminder = None
        if reminder is not None and (include_done or reminder["status"] == "pending"):
            return [reminder]
    if context.last_title:
        matches = find_reminders(str(context.last_title), include_done=include_done, limit=5)
        if len(matches) == 1:
            return matches
    return None


def _looks_like_contextual_reminder_reference(lowered: str, *, context_last_title: str | None) -> bool:
    if lowered in {"that", "it", "this reminder", "that reminder", "that one", "the one", "unknown"}:
        return True
    if any(token in lowered for token in ("one and only", "single reminder", "only reminder", "the one we have")):
        return True
    if context_last_title and lowered == str(context_last_title).strip().lower():
        return True
    return False


def _recent_list_bulk_matches(
    query: str,
    *,
    conversation_id: int | None,
    include_done: bool,
) -> list[dict[str, object]] | None:
    cleaned = _clean_text(query or "")
    context = get_reminder_context(conversation_id)
    if context is None or not context.last_listed_ids:
        return None
    if not cleaned or not _RECENT_LIST_BULK_RE.search(cleaned):
        return None

    matches: list[dict[str, object]] = []
    for reminder_id in context.last_listed_ids:
        try:
            reminder = get_reminder(int(reminder_id))
        except ValueError:
            continue
        if not include_done and reminder["status"] != "pending":
            continue
        matches.append(reminder)

    if not matches:
        raise ValueError("I couldn't find those recently listed reminders anymore.")
    return matches
def _infer_list_window(message: str) -> str:
    lower = message.lower()
    if "tomorrow" in lower:
        return "tomorrow"
    if "this week" in lower or "next 7 days" in lower:
        return "week"
    if "today" in lower:
        return "today"
    return "upcoming"

def _clean_text(value: str) -> str:
    return str(value or "").strip().rstrip("?.!,")

