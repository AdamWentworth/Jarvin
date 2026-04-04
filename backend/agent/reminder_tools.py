from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import re

from memory.reminders import (
    advance_due_at,
    complete_reminder,
    create_reminder,
    delete_reminder,
    find_reminders,
    list_due_reminders,
    list_reminders,
    normalize_recurrence,
    update_reminder,
)

DEFAULT_REMINDER_TIME = time(hour=9, minute=0)
WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

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
    r"^(?:please\s+)?(?:delete|remove|cancel)\s+(?:the\s+)?(?:reminder|task|to-?do)\s+(?P<query>.+)$",
    re.IGNORECASE,
)
_MOVE_RE = re.compile(
    r"^(?:please\s+)?(?:move|reschedule|delay|postpone)\s+(?:the\s+)?(?:reminder|task|to-?do)\s+(?P<query>.+?)\s+to\s+(?P<when>.+)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ReminderDraft:
    title: str
    due_at: datetime
    recurrence: str = "once"


def maybe_handle_reminder_request(text: str) -> str | None:
    message = (text or "").strip()
    if not message:
        return None

    if _LIST_ROUTINES_RE.search(message):
        return _list_reply(routines_only=True, window="upcoming")

    if _LIST_RE.search(message):
        return _list_reply(routines_only=False, window=_infer_list_window(message))

    complete_match = _COMPLETE_RE.search(message)
    if complete_match:
        return _complete_reply(_clean_text(complete_match.group("query")))

    delete_match = _DELETE_RE.search(message)
    if delete_match:
        return _delete_reply(_clean_text(delete_match.group("query")))

    move_match = _MOVE_RE.search(message)
    if move_match:
        return _move_reply(_clean_text(move_match.group("query")), _clean_text(move_match.group("when")))

    draft = _parse_reminder_draft(message)
    if draft is None:
        return None

    created = create_reminder(draft.title, due_at=draft.due_at, recurrence=draft.recurrence)
    recurrence_note = (
        f" This will repeat `{created['recurrence']}`."
        if created["recurrence"] != "once"
        else ""
    )
    return f"Saved reminder `{created['title']}` for `{_display_due(created['due_at'])}`.{recurrence_note}"


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
        return f"Saved reminder `{created['title']}` for `{_display_due(created['due_at'])}`."
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
        recurrence, due_at = _parse_recurring_schedule(schedule, time_hint=time_hint)
        return ReminderDraft(title=title, due_at=due_at, recurrence=recurrence)

    remind_match = _REMIND_ME_RE.match(message)
    if not remind_match:
        return None

    body = remind_match.group("body").strip()
    recurring_suffix = _ROUTINE_SUFFIX_RE.match(body)
    if recurring_suffix:
        title = _clean_text(recurring_suffix.group("title"))
        recurrence, due_at = _parse_recurring_schedule(
            recurring_suffix.group("schedule"),
            time_hint=recurring_suffix.group("time"),
        )
        return ReminderDraft(title=title, due_at=due_at, recurrence=recurrence)

    relative_match = _RELATIVE_RE.search(body)
    if relative_match:
        title = _clean_text(body[: relative_match.start()])
        due_at = _parse_due_text(relative_match.group(0))
        return ReminderDraft(title=title, due_at=due_at, recurrence="once")

    trailing_match = _TRAILING_SCHEDULE_RE.match(body)
    if trailing_match:
        title = _clean_text(trailing_match.group("title"))
        due_at = _parse_due_text(trailing_match.group("when"))
        return ReminderDraft(title=title, due_at=due_at, recurrence="once")

    time_only_match = _TIME_ONLY_RE.match(body)
    if time_only_match:
        title = _clean_text(time_only_match.group("title"))
        due_at = _parse_due_text(time_only_match.group("when"))
        return ReminderDraft(title=title, due_at=due_at, recurrence="once")

    raise ValueError(
        "I can save that reminder once you give me a time, like `remind me to call mom tomorrow at 5pm` "
        "or `remind me to stretch in 30 minutes`."
    )


def _list_reply(*, routines_only: bool, window: str) -> str:
    if routines_only:
        reminders = list_reminders(status="pending", recurrence="daily", limit=100) + list_reminders(
            status="pending",
            recurrence="weekday",
            limit=100,
        ) + list_reminders(status="pending", recurrence="weekly", limit=100)
        reminders = sorted(reminders, key=lambda item: item["due_at"])
        if not reminders:
            return "You do not have any active routines yet."
        lines = [
            f"- `{item['title']}` at `{_display_due(item['due_at'])}` (`{item['recurrence']}`)"
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
            if _parse_iso(item["due_at"]).date() == (now.date() + timedelta(days=1))
        ]
        label = "tomorrow"
    elif window == "week":
        now = datetime.now().astimezone()
        upper = now + timedelta(days=7)
        reminders = [
            item for item in list_reminders(status="pending", limit=100)
            if _parse_iso(item["due_at"]) <= upper
        ]
        label = "the next 7 days"
    else:
        reminders = list_reminders(status="pending", limit=20)
        label = "upcoming"

    if not reminders:
        return f"You do not have any pending reminders for {label}."

    lines = []
    for item in reminders[:20]:
        recurrence = f" ({item['recurrence']})" if item["recurrence"] != "once" else ""
        overdue = " [overdue]" if item["is_overdue"] else ""
        lines.append(f"- `{_display_due(item['due_at'])}` {item['title']}{recurrence}{overdue}")
    return f"Pending reminders for {label}:\n" + "\n".join(lines)


def _complete_reply(query: str) -> str:
    matches = find_reminders(query, include_done=False, limit=5)
    reminder = _pick_single_match(matches, query)
    updated = complete_reminder(int(reminder["id"]))
    if updated["recurrence"] == "once":
        return f"Marked `{updated['title']}` as done."
    return (
        f"Completed `{updated['title']}` for now. "
        f"The next `{updated['recurrence']}` reminder is set for `{_display_due(updated['due_at'])}`."
    )


def _delete_reply(query: str) -> str:
    matches = find_reminders(query, include_done=True, limit=5)
    reminder = _pick_single_match(matches, query)
    deleted = delete_reminder(int(reminder["id"]))
    return f"Deleted reminder `{deleted['title']}`."


def _move_reply(query: str, when_text: str) -> str:
    matches = find_reminders(query, include_done=False, limit=5)
    reminder = _pick_single_match(matches, query)
    due_at = _parse_due_text(when_text)
    updated = update_reminder(int(reminder["id"]), due_at=due_at)
    if updated["recurrence"] != "once":
        advanced = advance_due_at(updated["due_at"], updated["recurrence"], now=datetime.now().astimezone() - timedelta(seconds=1))
        updated = update_reminder(int(reminder["id"]), due_at=advanced)
    return f"Moved `{updated['title']}` to `{_display_due(updated['due_at'])}`."


def _pick_single_match(matches: list[dict[str, object]], query: str) -> dict[str, object]:
    if not matches:
        raise ValueError(f"I couldn't find a reminder matching '{query}'.")
    if len(matches) > 1:
        lines = [f"- `{item['title']}` due `{_display_due(str(item['due_at']))}`" for item in matches[:5]]
        raise ValueError("I found multiple matching reminders. Please be more specific:\n" + "\n".join(lines))
    return matches[0]


def _parse_recurring_schedule(schedule_text: str, *, time_hint: str | None) -> tuple[str, datetime]:
    raw = _clean_text(schedule_text).lower()
    now = datetime.now().astimezone()
    recurrence = "daily"
    due_date = now.date()

    if "weekday" in raw:
        recurrence = "weekday"
        while due_date.weekday() >= 5:
            due_date += timedelta(days=1)
    elif raw.startswith("weekly") or raw.startswith("every week"):
        recurrence = "weekly"
        for label, weekday in WEEKDAYS.items():
            if label in raw:
                due_date = _next_weekday(now.date(), weekday, allow_today=True)
                break
    else:
        recurrence = normalize_recurrence("daily")

    parsed_time = _extract_time(_clean_text(time_hint or "")) if time_hint else DEFAULT_REMINDER_TIME
    due_at = datetime.combine(due_date, parsed_time, tzinfo=now.tzinfo)
    if recurrence == "weekday" and due_at.weekday() >= 5:
        due_at = advance_due_at(due_at, recurrence, now=now)
    elif due_at <= now:
        due_at = advance_due_at(due_at, recurrence, now=now)
    return recurrence, due_at


def _parse_due_text(text: str) -> datetime:
    raw = _clean_text(text)
    now = datetime.now().astimezone()
    lower = raw.lower()

    relative_match = _RELATIVE_RE.search(lower)
    if relative_match:
        count = int(relative_match.group("count"))
        unit = relative_match.group("unit").lower()
        if unit.startswith("minute"):
            return now + timedelta(minutes=count)
        if unit.startswith("hour"):
            return now + timedelta(hours=count)
        return now + timedelta(days=count)

    parsed_date = _extract_explicit_date(lower) or _extract_relative_date(lower, now.date())
    parsed_time = _extract_time(lower)

    if parsed_date is None and parsed_time is None:
        raise ValueError(
            "I couldn't understand when to schedule that reminder. Try something like `tomorrow at 5pm` or `in 30 minutes`."
        )

    if parsed_date is None:
        parsed_date = now.date()
    if parsed_time is None:
        parsed_time = _default_time_for_phrase(lower)

    due_at = datetime.combine(parsed_date, parsed_time, tzinfo=now.tzinfo)
    if due_at <= now and parsed_date == now.date():
        due_at += timedelta(days=1)
    return due_at


def _extract_explicit_date(text: str) -> date | None:
    iso_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if iso_match:
        year, month, day = map(int, iso_match.groups())
        return date(year, month, day)

    slash_match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", text)
    if slash_match:
        month = int(slash_match.group(1))
        day = int(slash_match.group(2))
        year = int(slash_match.group(3)) if slash_match.group(3) else datetime.now().year
        if year < 100:
            year += 2000
        return date(year, month, day)
    return None


def _extract_relative_date(text: str, base_date: date) -> date | None:
    today = datetime.now().date()
    if "today" in text:
        return today
    if "tomorrow" in text:
        return today + timedelta(days=1)
    if "next week" in text:
        return base_date + timedelta(days=7)
    if "tonight" in text or "this evening" in text or "this afternoon" in text or "this morning" in text:
        return today

    for label, index in WEEKDAYS.items():
        if label in text:
            return _next_weekday(base_date, index, allow_today=not f"next {label}" in text)
    return None


def _next_weekday(base_date: date, weekday: int, *, allow_today: bool) -> date:
    days_ahead = (weekday - base_date.weekday()) % 7
    if days_ahead == 0 and not allow_today:
        days_ahead = 7
    return base_date + timedelta(days=days_ahead)


def _extract_time(text: str) -> time | None:
    if not text:
        return None
    if "noon" in text:
        return time(hour=12, minute=0)
    if "midnight" in text:
        return time(hour=0, minute=0)
    if "this morning" in text:
        return time(hour=9, minute=0)
    if "this afternoon" in text:
        return time(hour=15, minute=0)
    if "this evening" in text or "tonight" in text:
        return time(hour=19, minute=0)

    match = re.search(r"\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = match.group(3)
    if meridiem:
        meridiem = meridiem.lower()
        if meridiem == "pm" and hour != 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0
    if hour > 23 or minute > 59:
        raise ValueError("I couldn't understand that reminder time.")
    return time(hour=hour, minute=minute)


def _default_time_for_phrase(text: str) -> time:
    if "tonight" in text or "this evening" in text:
        return time(hour=19, minute=0)
    if "this afternoon" in text:
        return time(hour=15, minute=0)
    return DEFAULT_REMINDER_TIME


def _infer_list_window(message: str) -> str:
    lower = message.lower()
    if "tomorrow" in lower:
        return "tomorrow"
    if "this week" in lower or "next 7 days" in lower:
        return "week"
    if "today" in lower:
        return "today"
    return "upcoming"


def _display_due(value: str) -> str:
    due_at = _parse_iso(value)
    return due_at.strftime("%Y-%m-%d %I:%M %p")


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return parsed.astimezone()


def _clean_text(value: str) -> str:
    return str(value or "").strip().rstrip("?.!,")
