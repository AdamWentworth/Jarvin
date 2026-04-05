from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta


def parse_event_datetime(value: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        return datetime.now().astimezone()
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"Could not parse calendar event time '{value}'.") from exc
    if parsed.tzinfo is None:
        local_tz = datetime.now().astimezone().tzinfo
        return datetime.combine(parsed.date(), time.min, tzinfo=local_tz)
    return parsed


def parse_when_text(text: str, *, base_start: datetime) -> datetime:
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("I need the new date or time to reschedule that event.")

    tzinfo = base_start.tzinfo or datetime.now().astimezone().tzinfo
    lower = raw.lower()

    parsed_date = extract_explicit_date(lower) or extract_relative_date(lower, base_start.date())
    parsed_time = extract_time(lower)

    if parsed_date is None and parsed_time is None:
        raise ValueError(
            "I could not understand the new date or time. Try something like 'Friday at 2pm' or 'tomorrow at noon'."
        )

    if parsed_date is None:
        parsed_date = base_start.date()
    if parsed_time is None:
        parsed_time = base_start.timetz().replace(tzinfo=None)

    return datetime.combine(parsed_date, parsed_time, tzinfo=tzinfo)


def extract_explicit_date(text: str) -> date | None:
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


def extract_relative_date(text: str, base_date: date) -> date | None:
    today = datetime.now().date()
    if "today" in text:
        return today
    if "tomorrow" in text:
        return today + timedelta(days=1)
    if "next week" in text:
        return base_date + timedelta(days=7)

    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    for label, index in weekdays.items():
        if label in text:
            days_ahead = (index - base_date.weekday()) % 7
            if days_ahead == 0 or f"next {label}" in text:
                days_ahead = 7 if days_ahead == 0 else days_ahead + 7
            return base_date + timedelta(days=days_ahead)

    return None


def extract_time(text: str) -> time | None:
    if "noon" in text:
        return time(hour=12, minute=0)
    if "midnight" in text:
        return time(hour=0, minute=0)

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
        raise ValueError("I couldn't understand that time value.")

    return time(hour=hour, minute=minute)
