from __future__ import annotations

from datetime import datetime
import re

import config as cfg
from backend.agent.external_tools import (
    get_calendar_agenda,
    get_weather,
    google_calendar_credentials_configured,
    google_calendar_token_available,
)
from memory.conversation import get_user_profile
from memory.reminders import list_reminders

_BRIEF_RE = re.compile(
    r"(?:(?:give me|show me|read me|what(?:'s| is))\s+)?(?:(?:my|the)\s+)?(?:morning|daily|today(?:'s)?)\s+brief(?:\s+(?:for|in)\s+(?P<location>.+))?$",
    re.IGNORECASE,
)
_DAY_LOOK_RE = re.compile(
    r"(?:(?:brief me on|brief me about|what(?:'s| is)\s+)(?:my\s+)?)day(?:\s+(?:for|in)\s+(?P<location>.+))?(?:\s+look like)?$",
    re.IGNORECASE,
)


def maybe_handle_brief_request(text: str) -> str | None:
    message = (text or "").strip()
    if not message:
        return None

    brief_match = _BRIEF_RE.search(message)
    if brief_match:
        return build_morning_brief(location_hint=_clean_text(brief_match.group("location") or ""))

    day_match = _DAY_LOOK_RE.search(message)
    if day_match:
        return build_morning_brief(location_hint=_clean_text(day_match.group("location") or ""))

    return None


def handle_brief_command(rest: str) -> str:
    body = (rest or "").strip()
    if not body or body.lower() in {"morning", "today", "day"}:
        return build_morning_brief()
    return build_morning_brief(location_hint=body)


def build_morning_brief(*, location_hint: str | None = None) -> str:
    now = datetime.now().astimezone()
    profile = get_user_profile() or {}
    location = _clean_text(location_hint or "") or str(cfg.settings.default_weather_location or "").strip()

    sections: list[str] = [
        f"Morning brief for `{now.strftime('%A, %B %d')}`:",
    ]

    if profile.get("name"):
        sections.append(f"- Person: {profile['name']}")
    if profile.get("goal"):
        sections.append(f"- Current focus: {profile['goal']}")

    weather_line = _weather_section(location)
    if weather_line:
        sections.append(weather_line)

    sections.extend(_calendar_section())
    sections.extend(_reminder_section(now))
    return "\n".join(sections)


def _weather_section(location: str) -> str:
    if not location:
        return "- Weather: no default location is configured yet."
    try:
        weather = get_weather(location)
    except Exception as exc:
        return f"- Weather: I couldn't load weather for `{location}` just now. {str(exc).strip()}".rstrip()
    return (
        f"- Weather for `{weather.location_label}`: {weather.forecast_summary}, "
        f"{weather.temperature} now, feels like {weather.feels_like}. {weather.daily_outlook}."
    )


def _calendar_section() -> list[str]:
    if not google_calendar_credentials_configured():
        return ["- Calendar: not connected yet on this host."]
    if not google_calendar_token_available():
        return ["- Calendar: credentials are ready, but the host still needs authorization."]

    try:
        agenda = get_calendar_agenda(window_days=1)
    except Exception as exc:
        return [f"- Calendar: I couldn't load today's agenda. {str(exc).strip()}".rstrip()]

    if not agenda.events:
        return ["- Calendar: no upcoming events in the next 24 hours."]

    lines = ["- Calendar:"]
    for event in agenda.events[:5]:
        suffix = f" at {event.location}" if event.location else ""
        lines.append(f"  - `{event.starts_at}` {event.title}{suffix}")
    if len(agenda.events) > 5:
        lines.append(f"  - `...` plus {len(agenda.events) - 5} more event(s).")
    return lines


def _reminder_section(now: datetime) -> list[str]:
    reminders = list_reminders(status="pending", limit=50)
    due_today = []
    overdue = []
    for item in reminders:
        due_at = _parse_iso(str(item["due_at"]))
        if due_at.date() == now.date():
            due_today.append(item)
        elif bool(item.get("is_overdue")):
            overdue.append(item)

    lines: list[str] = []
    if overdue:
        lines.append("- Overdue reminders:")
        for item in overdue[:5]:
            recurrence = f" ({item['recurrence']})" if item["recurrence"] != "once" else ""
            lines.append(f"  - `{_display_due(str(item['due_at']))}` {item['title']}{recurrence}")

    if due_today:
        lines.append("- Today's reminders:")
        for item in due_today[:8]:
            recurrence = f" ({item['recurrence']})" if item["recurrence"] != "once" else ""
            lines.append(f"  - `{_display_due(str(item['due_at']))}` {item['title']}{recurrence}")
    elif not overdue:
        lines.append("- Reminders: nothing due today.")

    return lines


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return parsed.astimezone()


def _display_due(value: str) -> str:
    return _parse_iso(value).strftime("%I:%M %p")


def _clean_text(value: str) -> str:
    return str(value or "").strip().rstrip("?.!,")
