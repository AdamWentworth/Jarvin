from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
import sqlite3
import threading
from typing import Any

import config as cfg

VALID_RECURRENCES = {"once", "daily", "weekday", "weekly"}
WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is not None:
        return _conn

    db_path = Path(cfg.settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(str(db_path), check_same_thread=False)
    _conn.row_factory = sqlite3.Row

    try:
        if getattr(cfg.settings, "db_wal", False):
            _conn.execute("PRAGMA journal_mode=WAL;")
        _conn.execute("PRAGMA synchronous=NORMAL;")
        _conn.execute("PRAGMA foreign_keys=ON;")
    except Exception:
        pass

    _migrate(_conn)
    return _conn


def _migrate(conn: sqlite3.Connection) -> None:
    with conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                location TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                starts_at TEXT NOT NULL,
                ends_at TEXT NOT NULL,
                recurrence TEXT NOT NULL DEFAULT 'once',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS ix_calendar_events_starts_at
            ON calendar_events(starts_at);

            CREATE INDEX IF NOT EXISTS ix_calendar_events_recurrence_starts_at
            ON calendar_events(recurrence, starts_at);
            """
        )


def _reset_for_tests() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
    _conn = None


def normalize_recurrence(value: str | None) -> str:
    raw = str(value or "once").strip().lower()
    aliases = {
        "once": "once",
        "one-time": "once",
        "one_time": "once",
        "daily": "daily",
        "every day": "daily",
        "each day": "daily",
        "weekday": "weekday",
        "weekdays": "weekday",
        "every weekday": "weekday",
        "weekly": "weekly",
        "every week": "weekly",
    }
    normalized = aliases.get(raw, raw)
    if normalized.startswith("weekly:"):
        weekday_name = normalized.split(":", 1)[1].strip().lower()
        if weekday_name not in WEEKDAYS:
            raise ValueError(f"Unsupported weekly recurrence '{value}'.")
        return f"weekly:{weekday_name}"
    if normalized not in VALID_RECURRENCES:
        raise ValueError(f"Unsupported calendar recurrence '{value}'.")
    return normalized


def create_calendar_event(
    title: str,
    *,
    starts_at: datetime | str,
    ends_at: datetime | str,
    location: str = "",
    description: str = "",
    recurrence: str = "once",
) -> dict[str, Any]:
    title_text = str(title or "").strip()
    if not title_text:
        raise ValueError("Calendar event title cannot be empty.")

    start_dt = _normalize_datetime(starts_at)
    end_dt = _normalize_datetime(ends_at)
    if end_dt <= start_dt:
        raise ValueError("Calendar event end time must be after the start time.")

    recurrence_value = normalize_recurrence(recurrence)
    now_iso = _now_iso()
    conn = _connect()
    with _lock, conn:
        cur = conn.execute(
            """
            INSERT INTO calendar_events (
                title, location, description, starts_at, ends_at, recurrence, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                title_text,
                str(location or "").strip(),
                str(description or "").strip(),
                start_dt.isoformat(),
                end_dt.isoformat(),
                recurrence_value,
                now_iso,
                now_iso,
            ),
        )
        event_id = int(cur.lastrowid)
    return get_calendar_event(event_id)


def get_calendar_event(event_id: int | str) -> dict[str, Any]:
    conn = _connect()
    with _lock, conn:
        row = conn.execute(
            "SELECT * FROM calendar_events WHERE id = ?;",
            (int(event_id),),
        ).fetchone()
    if row is None:
        raise ValueError(f"Calendar event {event_id} does not exist.")
    return _row_to_dict(row)


def list_calendar_events(*, limit: int = 100) -> list[dict[str, Any]]:
    conn = _connect()
    with _lock, conn:
        rows = conn.execute(
            """
            SELECT * FROM calendar_events
            ORDER BY starts_at ASC, id ASC
            LIMIT ?;
            """,
            (max(1, int(limit)),),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def list_calendar_occurrences(
    *,
    lower: datetime,
    upper: datetime,
    limit: int = 50,
) -> list[dict[str, Any]]:
    events = list_calendar_events(limit=500)
    occurrences: list[dict[str, Any]] = []
    for event in events:
        occurrences.extend(_expand_event_occurrences(event, lower=lower, upper=upper, limit=limit))
    occurrences.sort(key=lambda item: item["starts_at"])
    return occurrences[: max(1, int(limit))]


def find_calendar_events(
    query: str,
    *,
    window_days: int = 30,
    limit: int = 5,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    text = str(query or "").strip().lower()
    if not text:
        raise ValueError("Calendar search text cannot be empty.")

    conn = _connect()
    with _lock, conn:
        rows = conn.execute(
            """
            SELECT * FROM calendar_events
            WHERE LOWER(title) LIKE ? OR LOWER(location) LIKE ? OR LOWER(description) LIKE ?
            ORDER BY starts_at ASC, id ASC
            LIMIT 100;
            """,
            (f"%{text}%", f"%{text}%", f"%{text}%"),
        ).fetchall()

    reference = now.astimezone() if now is not None else datetime.now().astimezone()
    lower = reference.replace(hour=0, minute=0, second=0, microsecond=0)
    upper = lower + timedelta(days=max(1, int(window_days)))
    matches: list[dict[str, Any]] = []
    for row in rows:
        event = _row_to_dict(row)
        occurrence = _next_occurrence_within_window(event, lower=lower, upper=upper)
        if occurrence is None:
            continue
        matches.append(occurrence)
    matches.sort(key=lambda item: item["starts_at"])
    return matches[: max(1, int(limit))]


def update_calendar_event(
    event_id: int | str,
    *,
    title: str | None = None,
    location: str | None = None,
    description: str | None = None,
    starts_at: datetime | str | None = None,
    ends_at: datetime | str | None = None,
    recurrence: str | None = None,
) -> dict[str, Any]:
    current = get_calendar_event(event_id)
    updates: dict[str, object] = {}
    if title is not None:
        title_text = str(title).strip()
        if not title_text:
            raise ValueError("Calendar event title cannot be empty.")
        updates["title"] = title_text
    if location is not None:
        updates["location"] = str(location).strip()
    if description is not None:
        updates["description"] = str(description).strip()
    if starts_at is not None:
        updates["starts_at"] = _normalize_datetime(starts_at).isoformat()
    if ends_at is not None:
        updates["ends_at"] = _normalize_datetime(ends_at).isoformat()
    if recurrence is not None:
        updates["recurrence"] = normalize_recurrence(recurrence)
    if not updates:
        return current

    effective_start = _normalize_datetime(str(updates.get("starts_at") or current["starts_at"]))
    effective_end = _normalize_datetime(str(updates.get("ends_at") or current["ends_at"]))
    if effective_end <= effective_start:
        raise ValueError("Calendar event end time must be after the start time.")

    updates["updated_at"] = _now_iso()
    assignments = ", ".join(f"{column} = ?" for column in updates)
    params = [*updates.values(), int(event_id)]
    conn = _connect()
    with _lock, conn:
        conn.execute(f"UPDATE calendar_events SET {assignments} WHERE id = ?;", params)
    return get_calendar_event(event_id)


def delete_calendar_event(event_id: int | str) -> dict[str, Any]:
    current = get_calendar_event(event_id)
    conn = _connect()
    with _lock, conn:
        conn.execute("DELETE FROM calendar_events WHERE id = ?;", (int(event_id),))
    return current


def next_calendar_occurrence(
    event_id: int | str,
    *,
    now: datetime | None = None,
    window_days: int = 90,
) -> dict[str, Any]:
    event = get_calendar_event(event_id)
    reference = now.astimezone() if now is not None else datetime.now().astimezone()
    lower = reference.replace(hour=0, minute=0, second=0, microsecond=0)
    upper = lower + timedelta(days=max(1, int(window_days)))
    occurrence = _next_occurrence_within_window(event, lower=lower, upper=upper)
    if occurrence is None:
        occurrence = _base_event_occurrence(event)
    return occurrence


def recurrence_label(value: str) -> str:
    recurrence = normalize_recurrence(value)
    if recurrence.startswith("weekly:"):
        weekday_name = recurrence.split(":", 1)[1]
        return f"weekly on {weekday_name.capitalize()}"
    return recurrence


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["id"] = int(data["id"])
    data["starts_at"] = _normalize_datetime(str(data["starts_at"])).isoformat()
    data["ends_at"] = _normalize_datetime(str(data["ends_at"])).isoformat()
    data["recurrence"] = normalize_recurrence(str(data.get("recurrence") or "once"))
    return data


def _base_event_occurrence(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": str(event["id"]),
        "title": str(event["title"]),
        "starts_at": str(event["starts_at"]),
        "ends_at": str(event["ends_at"]),
        "location": str(event.get("location") or ""),
        "description": str(event.get("description") or ""),
        "recurrence": str(event.get("recurrence") or "once"),
    }


def _expand_event_occurrences(
    event: dict[str, Any],
    *,
    lower: datetime,
    upper: datetime,
    limit: int,
) -> list[dict[str, Any]]:
    base_start = _normalize_datetime(str(event["starts_at"]))
    base_end = _normalize_datetime(str(event["ends_at"]))
    duration = base_end - base_start
    recurrence = normalize_recurrence(str(event.get("recurrence") or "once"))
    if recurrence == "once":
        if base_start < upper and base_end > lower:
            return [_base_event_occurrence(event)]
        return []

    occurrences: list[dict[str, Any]] = []
    cursor = _jump_to_window_start(base_start, recurrence, lower)
    while cursor < upper and len(occurrences) < max(1, int(limit)):
        end_cursor = cursor + duration
        if end_cursor > lower:
            occurrences.append(
                {
                    "event_id": str(event["id"]),
                    "title": str(event["title"]),
                    "starts_at": cursor.isoformat(),
                    "ends_at": end_cursor.isoformat(),
                    "location": str(event.get("location") or ""),
                    "description": str(event.get("description") or ""),
                    "recurrence": recurrence,
                }
            )
        cursor = _advance_occurrence(cursor, recurrence)
    return occurrences


def _next_occurrence_within_window(
    event: dict[str, Any],
    *,
    lower: datetime,
    upper: datetime,
) -> dict[str, Any] | None:
    occurrences = _expand_event_occurrences(event, lower=lower, upper=upper, limit=1)
    return occurrences[0] if occurrences else None


def _jump_to_window_start(start: datetime, recurrence: str, lower: datetime) -> datetime:
    recurrence_value = normalize_recurrence(recurrence)
    if recurrence_value == "once" or start >= lower:
        return start

    if recurrence_value == "daily":
        candidate = start + timedelta(days=max(0, (lower.date() - start.date()).days))
        while candidate < lower:
            candidate += timedelta(days=1)
        return candidate

    if recurrence_value.startswith("weekly"):
        days = max(0, (lower.date() - start.date()).days)
        candidate = start + timedelta(days=(days // 7) * 7)
        while candidate < lower:
            candidate += timedelta(days=7)
        return candidate

    candidate = datetime.combine(lower.date(), start.timetz().replace(tzinfo=None), tzinfo=start.tzinfo)
    if candidate < start:
        candidate = start
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    while candidate < lower:
        candidate = _advance_occurrence(candidate, recurrence_value)
    return candidate


def _advance_occurrence(start: datetime, recurrence: str) -> datetime:
    recurrence_value = normalize_recurrence(recurrence)
    if recurrence_value == "daily":
        return start + timedelta(days=1)
    if recurrence_value == "weekday":
        candidate = start + timedelta(days=1)
        while candidate.weekday() >= 5:
            candidate += timedelta(days=1)
        return candidate
    if recurrence_value == "weekly" or recurrence_value.startswith("weekly:"):
        return start + timedelta(days=7)
    return start


def _normalize_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value or "").strip()
        if not raw:
            raise ValueError("Calendar event date/time cannot be empty.")
        normalized = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(f"Could not parse calendar event date/time '{value}'.") from exc

    if parsed.tzinfo is None:
        local_tz = datetime.now().astimezone().tzinfo
        default_tz = local_tz if local_tz is not None else time.min.tzinfo
        parsed = parsed.replace(tzinfo=default_tz)
    return parsed.astimezone()


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()
