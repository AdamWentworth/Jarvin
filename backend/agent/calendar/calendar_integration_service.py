from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re

import config as cfg
from backend.agent.calendar.calendar_request_nlu import extract_date_hint, extract_time_hint, normalize_calendar_create_text
from backend.agent.calendar.calendar_datetime_utils import parse_event_datetime, parse_when_text
from backend.agent.integration_models import (
    CalendarAgendaResult,
    CalendarEventDetails,
    CalendarEventMatch,
    CalendarEventSummary,
)
from backend.agent.reminders.reminder_datetime_utils import parse_due_text, parse_recurring_schedule
from memory.calendar_events import (
    create_calendar_event,
    delete_calendar_event as delete_local_calendar_event,
    find_calendar_events as find_local_calendar_events,
    get_calendar_event,
    list_calendar_occurrences,
    next_calendar_occurrence,
    recurrence_label,
    update_calendar_event,
)

LOCAL_CALENDAR_LABEL = "Jarvin Calendar"
DEFAULT_EVENT_DURATION = timedelta(hours=1)
_SCHEDULE_PATTERN = (
    r"(?:every day|each day|daily|every weekday|each weekday|"
    r"weekly|every week(?:\s+on)?\s+\w+|every\s+"
    r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))"
)
_RECURRING_PREFIX_RE = re.compile(
    rf"^(?P<schedule>{_SCHEDULE_PATTERN})(?:\s+at\s+(?P<time>[^,]+?))?\s+(?P<title>.+)$",
    re.IGNORECASE,
)
_RECURRING_SUFFIX_RE = re.compile(
    rf"^(?P<title>.+?)\s+(?P<schedule>{_SCHEDULE_PATTERN})(?:\s+at\s+(?P<time>.+))?$",
    re.IGNORECASE,
)
_RELATIVE_RE = re.compile(r"\bin\s+\d+\s+(?:minutes?|hours?|days?)\b", re.IGNORECASE)
_TRAILING_SCHEDULE_RE = re.compile(
    r"^(?P<title>.+?)\s+(?P<when>(?:in\s+\d+\s+(?:minutes?|hours?|days?)|today|tomorrow|tonight|"
    r"this morning|this afternoon|this evening|next week|next\s+"
    r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?)"
    r"(?:\s+(?:at|around)\s+.+)?)$",
    re.IGNORECASE,
)
_TIME_ONLY_RE = re.compile(r"^(?P<title>.+?)\s+(?P<when>(?:at|around)\s+.+)$", re.IGNORECASE)
_DURATION_RE = re.compile(r"^(?P<body>.+?)\s+for\s+(?P<count>\d+)\s+(?P<unit>minutes?|hours?)$", re.IGNORECASE)


class CalendarCreateNeedsMoreDetail(ValueError):
    def __init__(
        self,
        message: str,
        *,
        title: str,
        missing: str,
        date_hint: str | None = None,
        time_hint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.title = title
        self.missing = missing
        self.date_hint = date_hint
        self.time_hint = time_hint


@dataclass(frozen=True)
class CalendarCreateDraft:
    title: str
    starts_at: datetime
    ends_at: datetime
    recurrence: str = "once"
    location: str = ""
    description: str = ""


def calendar_is_ready() -> bool:
    return True


def begin_calendar_setup() -> str:
    return (
        "Jarvin's built-in calendar is ready on this host. "
        f"Events are stored locally in `{cfg.settings.db_path}` under the `calendar_events` table, "
        "so no Google account or OAuth setup is required."
    )


def get_calendar_agenda(*, window_days: int = 7) -> CalendarAgendaResult:
    lower, upper = _calendar_window_bounds(window_days)
    limit = max(1, int(cfg.settings.calendar_max_events))
    occurrences = list_calendar_occurrences(lower=lower, upper=upper, limit=limit)
    events = [
        CalendarEventSummary(
            starts_at=_format_display_time(item["starts_at"]),
            title=str(item["title"]),
            location=str(item.get("location") or ""),
        )
        for item in occurrences
    ]
    return CalendarAgendaResult(
        calendar_id=LOCAL_CALENDAR_LABEL,
        window_days=max(1, int(window_days)),
        events=events,
    )


def create_calendar_event_from_text(text: str) -> CalendarEventSummary:
    draft = _parse_calendar_create_draft(text)
    created = create_calendar_event(
        draft.title,
        starts_at=draft.starts_at,
        ends_at=draft.ends_at,
        recurrence=draft.recurrence,
        location=draft.location,
        description=draft.description,
    )
    occurrence = next_calendar_occurrence(created["id"])
    return CalendarEventSummary(
        starts_at=_format_display_time(str(occurrence["starts_at"])),
        title=str(created["title"]),
        location=str(created.get("location") or ""),
    )


def find_calendar_events(query: str, *, window_days: int = 30, max_results: int = 5) -> list[CalendarEventMatch]:
    matches = find_local_calendar_events(query, window_days=window_days, limit=max_results)
    return [
        CalendarEventMatch(
            event_id=str(item["event_id"]),
            title=str(item["title"]),
            starts_at=str(item["starts_at"]),
            ends_at=str(item["ends_at"]),
            location=str(item.get("location") or ""),
            description=_display_description(str(item.get("description") or ""), str(item.get("recurrence") or "once")),
            calendar_id="local",
        )
        for item in matches
    ]


def get_calendar_event_details(event_id: str, *, calendar_id: str | None = None) -> CalendarEventDetails:
    stored = get_calendar_event(event_id)
    occurrence = next_calendar_occurrence(event_id)
    return CalendarEventDetails(
        event_id=str(stored["id"]),
        calendar_id="local",
        starts_at=_format_display_time(str(occurrence["starts_at"])),
        ends_at=_format_display_time(str(occurrence["ends_at"])),
        title=str(stored["title"]),
        location=str(stored.get("location") or ""),
        description=_display_description(str(stored.get("description") or ""), str(stored.get("recurrence") or "once")),
    )


def delete_calendar_event(event_id: str, *, calendar_id: str | None = None) -> CalendarEventSummary:
    stored = get_calendar_event(event_id)
    occurrence = next_calendar_occurrence(event_id)
    delete_local_calendar_event(event_id)
    return CalendarEventSummary(
        starts_at=_format_display_time(str(occurrence["starts_at"])),
        title=str(stored["title"]),
        location=str(stored.get("location") or ""),
    )


def update_calendar_event_fields(
    event_id: str,
    *,
    calendar_id: str | None = None,
    title: str | None = None,
    location: str | None = None,
    description: str | None = None,
    new_start_iso: str | None = None,
    new_end_iso: str | None = None,
) -> CalendarEventDetails:
    if new_start_iso is not None or new_end_iso is not None:
        if not new_start_iso or not new_end_iso:
            raise ValueError("Both the new start and end time are required when rescheduling an event.")
    updated = update_calendar_event(
        event_id,
        title=title,
        location=location,
        description=description,
        starts_at=new_start_iso,
        ends_at=new_end_iso,
    )
    occurrence = next_calendar_occurrence(updated["id"])
    return CalendarEventDetails(
        event_id=str(updated["id"]),
        calendar_id="local",
        starts_at=_format_display_time(str(occurrence["starts_at"])),
        ends_at=_format_display_time(str(occurrence["ends_at"])),
        title=str(updated["title"]),
        location=str(updated.get("location") or ""),
        description=_display_description(str(updated.get("description") or ""), str(updated.get("recurrence") or "once")),
    )


def reschedule_calendar_event(
    event_id: str,
    *,
    calendar_id: str | None = None,
    new_start_iso: str,
    new_end_iso: str,
) -> CalendarEventSummary:
    updated = update_calendar_event_fields(
        event_id,
        new_start_iso=new_start_iso,
        new_end_iso=new_end_iso,
    )
    return CalendarEventSummary(
        starts_at=updated.starts_at,
        title=updated.title,
        location=updated.location,
    )


def prepare_reschedule_times(event: CalendarEventMatch, when_text: str) -> tuple[str, str]:
    start_dt = parse_event_datetime(event.starts_at)
    end_dt = parse_event_datetime(event.ends_at)
    duration = end_dt - start_dt if end_dt > start_dt else DEFAULT_EVENT_DURATION
    new_start = parse_when_text(when_text, base_start=start_dt)
    new_end = new_start + duration
    return new_start.isoformat(), new_end.isoformat()


def _parse_calendar_create_draft(text: str) -> CalendarCreateDraft:
    details = _clean_text(normalize_calendar_create_text(text) or text)
    if not details:
        raise ValueError("I need event details before I can create a calendar event.")

    body, duration = _extract_duration(details)
    recurring = _parse_recurring_draft(body, duration=duration)
    if recurring is not None:
        return recurring

    single = _parse_one_time_draft(body, duration=duration)
    if single is not None:
        return single

    raise ValueError(
        "I can add that once you give me a date and time, like `lunch with Sam tomorrow at noon` "
        "or `project sync every Saturday at 9am`."
    )


def _parse_recurring_draft(text: str, *, duration: timedelta) -> CalendarCreateDraft | None:
    prefix_match = _RECURRING_PREFIX_RE.match(text)
    if prefix_match:
        schedule = prefix_match.group("schedule")
        time_hint = prefix_match.group("time")
        title = _clean_text(prefix_match.group("title"))
        recurrence, starts_at = parse_recurring_schedule(schedule, time_hint=time_hint)
        return _build_create_draft(title, starts_at, duration=duration, recurrence=recurrence)

    suffix_match = _RECURRING_SUFFIX_RE.match(text)
    if suffix_match:
        title = _clean_text(suffix_match.group("title"))
        schedule = suffix_match.group("schedule")
        time_hint = suffix_match.group("time")
        recurrence, starts_at = parse_recurring_schedule(schedule, time_hint=time_hint)
        return _build_create_draft(title, starts_at, duration=duration, recurrence=recurrence)

    return None


def _parse_one_time_draft(text: str, *, duration: timedelta) -> CalendarCreateDraft | None:
    relative_match = _RELATIVE_RE.search(text)
    if relative_match:
        title = _clean_text(text[: relative_match.start()])
        starts_at = parse_due_text(relative_match.group(0))
        return _build_create_draft(title, starts_at, duration=duration)

    trailing_match = _TRAILING_SCHEDULE_RE.match(text)
    if trailing_match:
        title = _clean_text(trailing_match.group("title"))
        when_text = _clean_text(trailing_match.group("when")) or ""
        if extract_time_hint(when_text) is None:
            _raise_missing_time(title, when_text)
        starts_at = parse_due_text(when_text)
        return _build_create_draft(title, starts_at, duration=duration)

    time_only_match = _TIME_ONLY_RE.match(text)
    if time_only_match:
        title = _clean_text(time_only_match.group("title"))
        when_text = _clean_text(time_only_match.group("when")) or ""
        _raise_missing_date(title, when_text)

    return None


def _build_create_draft(
    title: str,
    starts_at: datetime,
    *,
    duration: timedelta,
    recurrence: str = "once",
) -> CalendarCreateDraft:
    title_text = _clean_text(title)
    if not title_text:
        raise ValueError("I need an event title before I can create that calendar event.")
    start_dt = starts_at.astimezone() if starts_at.tzinfo is not None else starts_at.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return CalendarCreateDraft(
        title=title_text,
        starts_at=start_dt,
        ends_at=start_dt + duration,
        recurrence=recurrence,
    )


def _extract_duration(text: str) -> tuple[str, timedelta]:
    match = _DURATION_RE.match(text)
    if not match:
        return text, DEFAULT_EVENT_DURATION

    count = max(1, int(match.group("count")))
    unit = match.group("unit").lower()
    duration = timedelta(minutes=count) if unit.startswith("minute") else timedelta(hours=count)
    return _clean_text(match.group("body")), duration


def _display_description(description: str, recurrence: str) -> str:
    details = str(description or "").strip()
    recurrence_note = ""
    if str(recurrence or "once").strip().lower() != "once":
        recurrence_note = f"Repeats: {recurrence_label(recurrence)}."
    if details and recurrence_note:
        return f"{details}\n{recurrence_note}"
    return details or recurrence_note


def _calendar_window_bounds(window_days: int) -> tuple[datetime, datetime]:
    days = max(1, int(window_days))
    local_now = datetime.now().astimezone()
    lower = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    upper = lower + timedelta(days=days)
    return lower, upper


def _format_display_time(value: str) -> str:
    return parse_event_datetime(value).astimezone().strftime("%Y-%m-%d %I:%M %p")


def _clean_text(value: str) -> str:
    return str(value or "").strip().rstrip("?.!,")


def _raise_missing_time(title: str, when_text: str) -> None:
    title_text = _clean_text(title)
    date_hint = extract_date_hint(when_text) or _clean_text(when_text)
    raise CalendarCreateNeedsMoreDetail(
        f"I can put `{title_text}` on your calendar for `{date_hint}`. What time should I use?",
        title=title_text,
        missing="time",
        date_hint=date_hint,
    )


def _raise_missing_date(title: str, when_text: str) -> None:
    title_text = _clean_text(title)
    time_hint = _normalize_time_hint_for_prompt(when_text)
    raise CalendarCreateNeedsMoreDetail(
        f"I can schedule `{title_text}` {time_hint}. What day should I put it on?",
        title=title_text,
        missing="date",
        time_hint=time_hint,
    )


def _normalize_time_hint_for_prompt(value: str) -> str:
    hint = _clean_text(value).lower()
    if hint.startswith("around "):
        hint = re.sub(r"^around\s+", "at ", hint)
    elif not hint.startswith(("at ", "this ", "tonight")):
        hint = f"at {hint}"
    return hint
