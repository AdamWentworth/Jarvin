from __future__ import annotations

from datetime import date, datetime, time, timedelta
import re

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


def parse_recurring_schedule(schedule_text: str, *, time_hint: str | None) -> tuple[str, datetime]:
    schedule = str(schedule_text or "").strip().lower()
    if not schedule:
        raise ValueError("Tell me how often the reminder should repeat, like `every day at 8am`.")

    if "weekday" in schedule:
        recurrence = "weekday"
        target_date = _next_weekday(date.today(), 0, allow_today=True)
    elif any(day in schedule for day in WEEKDAYS):
        matched_day = next(day for day in WEEKDAYS if day in schedule)
        recurrence = f"weekly:{matched_day}"
        target_date = _next_weekday(date.today(), WEEKDAYS[matched_day], allow_today=True)
    elif "week" in schedule:
        recurrence = "weekly"
        target_date = date.today() + timedelta(days=7)
    else:
        recurrence = "daily"
        target_date = date.today()

    parsed_time = _extract_time(time_hint or schedule) or DEFAULT_REMINDER_TIME
    return recurrence, datetime.combine(target_date, parsed_time)


def parse_due_text(text: str) -> datetime:
    now = datetime.now()
    lower = str(text or "").strip().lower()
    if not lower:
        raise ValueError("Tell me when the reminder should happen.")

    relative_match = re.search(r"in\s+(?P<count>\d+)\s+(?P<unit>minutes?|hours?|days?)", lower)
    if relative_match:
        count = int(relative_match.group("count"))
        unit = relative_match.group("unit")
        if unit.startswith("minute"):
            return now + timedelta(minutes=count)
        if unit.startswith("hour"):
            return now + timedelta(hours=count)
        return now + timedelta(days=count)

    explicit_date = _extract_explicit_date(lower)
    target_date = explicit_date or _extract_relative_date(lower, now.date()) or now.date()
    parsed_time = _extract_time(lower)
    if parsed_time is None:
        parsed_time = _default_time_for_phrase(lower)
    return datetime.combine(target_date, parsed_time)


def display_due(value: str) -> str:
    return parse_iso(value).strftime("%Y-%m-%d %I:%M %p")


def _extract_explicit_date(text: str) -> date | None:
    iso_match = re.search(r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})", text)
    if iso_match:
        return date(
            int(iso_match.group("year")),
            int(iso_match.group("month")),
            int(iso_match.group("day")),
        )

    slash_match = re.search(r"(?P<month>\d{1,2})/(?P<day>\d{1,2})(?:/(?P<year>\d{2,4}))?", text)
    if slash_match:
        year_text = slash_match.group("year")
        if year_text:
            year = int(year_text)
            if year < 100:
                year += 2000
        else:
            year = date.today().year
        return date(year, int(slash_match.group("month")), int(slash_match.group("day")))

    return None


def _extract_relative_date(text: str, base_date: date) -> date | None:
    if "tomorrow" in text:
        return base_date + timedelta(days=1)
    if "today" in text or "tonight" in text or "this morning" in text or "this afternoon" in text or "this evening" in text:
        return base_date
    if "next week" in text:
        return base_date + timedelta(days=7)
    for weekday, index in WEEKDAYS.items():
        token = f"next {weekday}"
        if token in text:
            return _next_weekday(base_date, index, allow_today=False)
        if re.search(rf"\b{weekday}\b", text):
            return _next_weekday(base_date, index, allow_today=True)
    return None


def _next_weekday(base_date: date, weekday: int, *, allow_today: bool) -> date:
    days_ahead = (weekday - base_date.weekday()) % 7
    if days_ahead == 0 and not allow_today:
        days_ahead = 7
    return base_date + timedelta(days=days_ahead)


def _extract_time(text: str) -> time | None:
    if not text:
        return None

    colon_match = re.search(r"\b(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<meridiem>am|pm)\b", text, re.IGNORECASE)
    if colon_match:
        minutes = _time_match_to_minutes(
            colon_match.group("hour"),
            colon_match.group("minute"),
            colon_match.group("meridiem"),
        )
        return time(hour=minutes // 60, minute=minutes % 60)

    noon_alias = re.search(r"\b(noon|midday|lunch)\b", text, re.IGNORECASE)
    if noon_alias:
        return time(hour=12, minute=0)

    midnight_alias = re.search(r"\bmidnight\b", text, re.IGNORECASE)
    if midnight_alias:
        return time(hour=0, minute=0)

    twenty_four = re.search(r"\b(?P<hour>[01]?\d|2[0-3]):(?P<minute>\d{2})\b", text)
    if twenty_four:
        return time(hour=int(twenty_four.group("hour")), minute=int(twenty_four.group("minute")))

    named = re.search(r"\b(?P<hour>\d{1,2})\s*(?P<meridiem>am|pm)\b", text, re.IGNORECASE)
    if named:
        minutes = _time_match_to_minutes(named.group("hour"), None, named.group("meridiem"))
        return time(hour=minutes // 60, minute=minutes % 60)

    return None


def _time_match_to_minutes(hour_text: str, minute_text: str | None, meridiem_text: str | None) -> int:
    hour = int(hour_text)
    minute = int(minute_text or 0)
    meridiem = (meridiem_text or "").lower()
    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    return hour * 60 + minute


def _default_time_for_phrase(text: str) -> time:
    if "morning" in text:
        return time(hour=9, minute=0)
    if "afternoon" in text:
        return time(hour=15, minute=0)
    if "evening" in text or "tonight" in text:
        return time(hour=19, minute=0)
    if "lunch" in text or "midday" in text or "noon" in text:
        return time(hour=12, minute=0)
    return DEFAULT_REMINDER_TIME


def parse_iso(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return datetime.fromisoformat(normalized)
