from __future__ import annotations

from datetime import datetime, timedelta
import re

import config as cfg
from backend.agent.briefing.brief_request_planner import (
    maybe_plan_brief_request,
    remember_brief_context,
)
from backend.agent.integration_facade import (
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


def maybe_handle_brief_request(text: str, *, conversation_id: int | None = None) -> str | None:
    message = (text or "").strip()
    if not message:
        return None

    plan = maybe_plan_brief_request(message, conversation_id=conversation_id)
    if plan is not None and plan.is_brief_request:
        reply = build_morning_brief(location_hint=plan.location_hint, day_offset=plan.day_offset)
        remember_brief_context(
            conversation_id,
            day_offset=plan.day_offset,
            location_hint=plan.location_hint,
        )
        return reply

    brief_match = _BRIEF_RE.search(message)
    if brief_match:
        reply = build_morning_brief(location_hint=_clean_text(brief_match.group("location") or ""))
        remember_brief_context(conversation_id, day_offset=0, location_hint=_clean_text(brief_match.group("location") or "") or None)
        return reply

    day_match = _DAY_LOOK_RE.search(message)
    if day_match:
        reply = build_morning_brief(location_hint=_clean_text(day_match.group("location") or ""))
        remember_brief_context(conversation_id, day_offset=0, location_hint=_clean_text(day_match.group("location") or "") or None)
        return reply

    return None


def handle_brief_command(rest: str) -> str:
    body = (rest or "").strip()
    if not body or body.lower() in {"morning", "today", "day"}:
        return build_morning_brief()
    if body.lower() == "tomorrow":
        return build_morning_brief(day_offset=1)
    return build_morning_brief(location_hint=body)


def build_morning_brief(*, location_hint: str | None = None, day_offset: int = 0) -> str:
    now = datetime.now().astimezone()
    day_offset = max(0, int(day_offset))
    target_date = (now + timedelta(days=day_offset)).date()
    profile = get_user_profile() or {}
    location = _clean_text(location_hint or "") or str(cfg.settings.default_weather_location or "").strip()

    sections: list[str] = [
        _brief_heading(now, day_offset),
    ]

    if profile.get("name"):
        sections.append(f"- Person: {profile['name']}")
    if profile.get("goal"):
        sections.append(f"- Current focus: {profile['goal']}")

    weather_line = _weather_section(location, day_offset=day_offset)
    if weather_line:
        sections.append(weather_line)

    sections.extend(_calendar_section(target_date=target_date, day_offset=day_offset))
    sections.extend(_reminder_section(target_date=target_date, now=now, day_offset=day_offset))
    return "\n".join(sections)


def _weather_section(location: str, *, day_offset: int) -> str:
    if not location:
        return "- Weather: no default location is configured yet."
    try:
        weather = get_weather(location, day_offset=day_offset)
    except Exception as exc:
        return f"- Weather: I couldn't load weather for `{location}` just now. {str(exc).strip()}".rstrip()
    return (
        f"- Weather for `{weather.location_label}` ({weather.target_label}): {weather.forecast_summary}, "
        f"{weather.temperature}{' now' if weather.is_current_day else ''}, feels like {weather.feels_like}. {weather.daily_outlook}."
    )


def _calendar_section(*, target_date, day_offset: int) -> list[str]:
    if not google_calendar_credentials_configured():
        return ["- Calendar: not connected yet on this host."]
    if not google_calendar_token_available():
        return ["- Calendar: credentials are ready, but the host still needs authorization."]

    try:
        agenda = get_calendar_agenda(window_days=max(1, day_offset + 1))
    except Exception as exc:
        return [f"- Calendar: I couldn't load that day's agenda. {str(exc).strip()}".rstrip()]

    events = []
    for event in agenda.events:
        try:
            parsed = _parse_event_time(event.starts_at)
        except Exception:
            continue
        if parsed.date() == target_date:
            events.append(event)

    if not events:
        label = "today" if day_offset == 0 else target_date.strftime("%A")
        return [f"- Calendar: no events found for {label}."]

    lines = ["- Calendar:"]
    for event in events[:5]:
        suffix = f" at {event.location}" if event.location else ""
        lines.append(f"  - `{event.starts_at}` {event.title}{suffix}")
    if len(events) > 5:
        lines.append(f"  - `...` plus {len(events) - 5} more event(s).")
    return lines


def _reminder_section(*, target_date, now: datetime, day_offset: int) -> list[str]:
    reminders = list_reminders(status="pending", limit=50)
    due_today = []
    overdue = []
    for item in reminders:
        due_at = _parse_iso(str(item["due_at"]))
        if due_at.date() == target_date:
            due_today.append(item)
        elif day_offset == 0 and bool(item.get("is_overdue")):
            overdue.append(item)

    lines: list[str] = []
    if overdue and day_offset == 0:
        lines.append("- Overdue reminders:")
        for item in overdue[:5]:
            recurrence = f" ({item['recurrence']})" if item["recurrence"] != "once" else ""
            lines.append(f"  - `{_display_due(str(item['due_at']))}` {item['title']}{recurrence}")

    if due_today:
        label = "Today's reminders:" if day_offset == 0 else f"Reminders for {target_date.strftime('%A')}:"
        lines.append(f"- {label}")
        for item in due_today[:8]:
            recurrence = f" ({item['recurrence']})" if item["recurrence"] != "once" else ""
            lines.append(f"  - `{_display_due(str(item['due_at']))}` {item['title']}{recurrence}")
    elif not overdue:
        label = "today" if day_offset == 0 else target_date.strftime("%A")
        lines.append(f"- Reminders: nothing due for {label}.")

    return lines


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return parsed.astimezone()


def _display_due(value: str) -> str:
    return _parse_iso(value).strftime("%I:%M %p")


def _parse_event_time(value: str) -> datetime:
    raw = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.strptime(raw, "%Y-%m-%d %I:%M %p")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return parsed.astimezone()


def _brief_heading(now: datetime, day_offset: int) -> str:
    target = now + timedelta(days=day_offset)
    if day_offset == 0:
        return f"Morning brief for `{target.strftime('%A, %B %d')}`:"
    return f"Brief for `{target.strftime('%A, %B %d')}`:"


def _clean_text(value: str) -> str:
    return str(value or "").strip().rstrip("?.!,")

