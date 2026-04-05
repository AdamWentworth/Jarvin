from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import config as cfg
from backend.agent.calendar.calendar_datetime_utils import parse_event_datetime, parse_when_text
from backend.agent.integration_models import (
    CalendarAgendaResult,
    CalendarEventDetails,
    CalendarEventMatch,
    CalendarEventSummary,
)

GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def google_calendar_credentials_configured() -> bool:
    return Path(cfg.settings.google_calendar_credentials_file).resolve().is_file()


def google_calendar_token_available() -> bool:
    return Path(cfg.settings.google_calendar_token_file).resolve().is_file()


def begin_google_calendar_auth() -> str:
    creds = _load_google_credentials(interactive=True)
    token_path = Path(cfg.settings.google_calendar_token_file).resolve()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return f"Google Calendar authorization complete on the host machine. Token saved to `{token_path}`."


def get_calendar_agenda(*, window_days: int = 7) -> CalendarAgendaResult:
    service = _get_calendar_service(interactive=False)
    now = datetime.now(timezone.utc)
    upper = now + timedelta(days=max(1, int(window_days)))
    events_result = (
        service.events()
        .list(
            calendarId=cfg.settings.google_calendar_id,
            timeMin=now.isoformat(),
            timeMax=upper.isoformat(),
            maxResults=max(1, int(cfg.settings.google_calendar_max_events)),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    items = events_result.get("items", [])
    events = [
        CalendarEventSummary(
            starts_at=_format_google_event_start(item.get("start", {})),
            title=item.get("summary") or "(untitled event)",
            location=item.get("location") or "",
        )
        for item in items
    ]
    return CalendarAgendaResult(
        calendar_id=cfg.settings.google_calendar_id,
        window_days=max(1, int(window_days)),
        events=events,
    )


def create_calendar_event_from_text(text: str) -> CalendarEventSummary:
    details = str(text or "").strip()
    if not details:
        raise ValueError("I need event details before I can create a calendar event.")

    service = _get_calendar_service(interactive=False)
    event = (
        service.events()
        .quickAdd(
            calendarId=cfg.settings.google_calendar_id,
            text=details,
            sendUpdates="none",
        )
        .execute()
    )
    return _event_to_summary(event)


def find_calendar_events(query: str, *, window_days: int = 30, max_results: int = 5) -> list[CalendarEventMatch]:
    text = str(query or "").strip()
    if not text:
        raise ValueError("I need an event name or description to search your calendar.")

    service = _get_calendar_service(interactive=False)
    now = datetime.now(timezone.utc)
    upper = now + timedelta(days=max(1, int(window_days)))
    response = (
        service.events()
        .list(
            calendarId=cfg.settings.google_calendar_id,
            timeMin=now.isoformat(),
            timeMax=upper.isoformat(),
            q=text,
            maxResults=max(1, int(max_results)),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return [_event_to_match(item) for item in response.get("items", [])]


def get_calendar_event_details(event_id: str) -> CalendarEventDetails:
    target_id = str(event_id or "").strip()
    if not target_id:
        raise ValueError("Missing calendar event id.")

    service = _get_calendar_service(interactive=False)
    event = service.events().get(calendarId=cfg.settings.google_calendar_id, eventId=target_id).execute()
    return _event_to_details(event)


def delete_calendar_event(event_id: str) -> CalendarEventSummary:
    target_id = str(event_id or "").strip()
    if not target_id:
        raise ValueError("Missing calendar event id.")

    service = _get_calendar_service(interactive=False)
    event = service.events().get(calendarId=cfg.settings.google_calendar_id, eventId=target_id).execute()
    summary = _event_to_summary(event)
    service.events().delete(calendarId=cfg.settings.google_calendar_id, eventId=target_id, sendUpdates="none").execute()
    return summary


def update_calendar_event_fields(
    event_id: str,
    *,
    title: str | None = None,
    location: str | None = None,
    description: str | None = None,
    new_start_iso: str | None = None,
    new_end_iso: str | None = None,
) -> CalendarEventDetails:
    target_id = str(event_id or "").strip()
    if not target_id:
        raise ValueError("Missing calendar event id.")

    body: dict[str, Any] = {}
    if title is not None:
        body["summary"] = title
    if location is not None:
        body["location"] = location
    if description is not None:
        body["description"] = description

    service = _get_calendar_service(interactive=False)
    if new_start_iso is not None or new_end_iso is not None:
        if not new_start_iso or not new_end_iso:
            raise ValueError("Both the new start and end time are required when rescheduling an event.")
        existing = service.events().get(calendarId=cfg.settings.google_calendar_id, eventId=target_id).execute()
        timezone_name = (
            existing.get("start", {}).get("timeZone")
            or existing.get("end", {}).get("timeZone")
            or "UTC"
        )
        body["start"] = {"dateTime": new_start_iso, "timeZone": timezone_name}
        body["end"] = {"dateTime": new_end_iso, "timeZone": timezone_name}

    if not body:
        raise ValueError("I need at least one calendar field to update.")

    patched = (
        service.events()
        .patch(
            calendarId=cfg.settings.google_calendar_id,
            eventId=target_id,
            body=body,
            sendUpdates="none",
        )
        .execute()
    )
    return _event_to_details(patched)


def reschedule_calendar_event(event_id: str, *, new_start_iso: str, new_end_iso: str) -> CalendarEventSummary:
    target_id = str(event_id or "").strip()
    if not target_id:
        raise ValueError("Missing calendar event id.")

    patched = update_calendar_event_fields(
        target_id,
        new_start_iso=new_start_iso,
        new_end_iso=new_end_iso,
    )
    return CalendarEventSummary(
        starts_at=patched.starts_at,
        title=patched.title,
        location=patched.location,
    )


def prepare_reschedule_times(event: CalendarEventMatch, when_text: str) -> tuple[str, str]:
    start_dt = parse_event_datetime(event.starts_at)
    end_dt = parse_event_datetime(event.ends_at)
    duration = end_dt - start_dt if end_dt > start_dt else timedelta(hours=1)
    new_start = parse_when_text(when_text, base_start=start_dt)
    new_end = new_start + duration
    return new_start.isoformat(), new_end.isoformat()


def _load_google_credentials(*, interactive: bool):
    creds_path = Path(cfg.settings.google_calendar_credentials_file).resolve()
    if not creds_path.is_file():
        raise ValueError(
            "Google Calendar credentials are not configured yet. "
            f"Put your OAuth desktop client JSON at `{creds_path}` first."
        )

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise RuntimeError(
            "Google Calendar dependencies are missing. Install the updated Jarvin requirements first."
        ) from exc

    token_path = Path(cfg.settings.google_calendar_token_file).resolve()
    creds = None
    if token_path.is_file():
        creds = Credentials.from_authorized_user_file(str(token_path), GOOGLE_CALENDAR_SCOPES)

    if creds and not creds.has_scopes(GOOGLE_CALENDAR_SCOPES):
        if not interactive:
            raise ValueError(
                "Google Calendar needs to be re-authorized on this host because Jarvin now requests broader calendar permissions. "
                "Ask me to connect your Google Calendar again."
            )
        creds = None

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    if not interactive:
        raise ValueError(
            "Google Calendar is not authorized on this host yet. Ask me to connect your Google Calendar and I will start the OAuth flow."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), GOOGLE_CALENDAR_SCOPES)
    return flow.run_local_server(port=0)


def _get_calendar_service(*, interactive: bool):
    creds = _load_google_credentials(interactive=interactive)
    token_path = Path(cfg.settings.google_calendar_token_file).resolve()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Google Calendar dependencies are missing. Install the updated Jarvin requirements first."
        ) from exc
    return build("calendar", "v3", credentials=creds)


def _format_google_event_start(start: dict[str, Any]) -> str:
    value = start.get("dateTime") or start.get("date") or ""
    if not value:
        return "Unknown time"
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return value
    if parsed.tzinfo is None:
        return parsed.strftime("%Y-%m-%d")
    return parsed.astimezone().strftime("%Y-%m-%d %I:%M %p")


def _event_to_summary(event: dict[str, Any]) -> CalendarEventSummary:
    return CalendarEventSummary(
        starts_at=_format_google_event_start(event.get("start", {})),
        title=event.get("summary") or "(untitled event)",
        location=event.get("location") or "",
    )


def _event_to_match(event: dict[str, Any]) -> CalendarEventMatch:
    return CalendarEventMatch(
        event_id=event.get("id") or "",
        title=event.get("summary") or "(untitled event)",
        starts_at=event.get("start", {}).get("dateTime") or event.get("start", {}).get("date") or "",
        ends_at=event.get("end", {}).get("dateTime") or event.get("end", {}).get("date") or "",
        location=event.get("location") or "",
        description=event.get("description") or "",
    )


def _event_to_details(event: dict[str, Any]) -> CalendarEventDetails:
    return CalendarEventDetails(
        event_id=event.get("id") or "",
        calendar_id=event.get("organizer", {}).get("email") or cfg.settings.google_calendar_id,
        starts_at=_format_google_event_start(event.get("start", {})),
        ends_at=_format_google_event_start(event.get("end", {})),
        title=event.get("summary") or "(untitled event)",
        location=event.get("location") or "",
        description=event.get("description") or "",
    )

