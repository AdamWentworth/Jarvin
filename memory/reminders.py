from __future__ import annotations

from datetime import datetime, time, timedelta
from pathlib import Path
import sqlite3
import threading
from typing import Any

import config as cfg

VALID_RECURRENCES = {"once", "daily", "weekday", "weekly"}
VALID_STATUSES = {"pending", "done", "canceled"}

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
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                due_at TEXT NOT NULL,
                recurrence TEXT NOT NULL DEFAULT 'once',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            );

            CREATE INDEX IF NOT EXISTS ix_reminders_status_due
            ON reminders(status, due_at);

            CREATE INDEX IF NOT EXISTS ix_reminders_recurrence_due
            ON reminders(recurrence, due_at);
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
        "workday": "weekday",
        "workdays": "weekday",
        "weekly": "weekly",
        "every week": "weekly",
    }
    normalized = aliases.get(raw, raw)
    if normalized not in VALID_RECURRENCES:
        raise ValueError(f"Unsupported reminder recurrence '{value}'.")
    return normalized


def normalize_status(value: str | None) -> str:
    raw = str(value or "pending").strip().lower()
    if raw not in VALID_STATUSES:
        raise ValueError(f"Unsupported reminder status '{value}'.")
    return raw


def create_reminder(
    title: str,
    *,
    due_at: datetime | str,
    recurrence: str = "once",
    notes: str = "",
) -> dict[str, Any]:
    title_text = str(title or "").strip()
    if not title_text:
        raise ValueError("Reminder title cannot be empty.")

    due = _normalize_datetime(due_at)
    recurrence_value = normalize_recurrence(recurrence)
    now_iso = _now_iso()
    conn = _connect()
    with _lock, conn:
        cur = conn.execute(
            """
            INSERT INTO reminders (title, notes, due_at, recurrence, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?);
            """,
            (title_text, str(notes or "").strip(), due.isoformat(), recurrence_value, now_iso, now_iso),
        )
        reminder_id = int(cur.lastrowid)
    return get_reminder(reminder_id)


def get_reminder(reminder_id: int) -> dict[str, Any]:
    conn = _connect()
    with _lock, conn:
        row = conn.execute("SELECT * FROM reminders WHERE id = ?;", (int(reminder_id),)).fetchone()
    if row is None:
        raise ValueError(f"Reminder {reminder_id} does not exist.")
    return _row_to_dict(row)


def list_reminders(
    *,
    status: str | None = "pending",
    recurrence: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    conn = _connect()
    clauses: list[str] = []
    params: list[object] = []
    if status is not None:
        clauses.append("status = ?")
        params.append(normalize_status(status))
    if recurrence is not None:
        clauses.append("recurrence = ?")
        params.append(normalize_recurrence(recurrence))

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"""
        SELECT * FROM reminders
        {where}
        ORDER BY
            CASE status WHEN 'pending' THEN 0 WHEN 'done' THEN 1 ELSE 2 END,
            due_at ASC,
            id ASC
        LIMIT ?;
    """
    params.append(max(1, int(limit)))
    with _lock, conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(row) for row in rows]


def list_due_reminders(*, minutes_ahead: int = 0, limit: int = 20) -> list[dict[str, Any]]:
    conn = _connect()
    upper = datetime.now().astimezone() + timedelta(minutes=max(0, int(minutes_ahead)))
    with _lock, conn:
        rows = conn.execute(
            """
            SELECT * FROM reminders
            WHERE status = 'pending' AND due_at <= ?
            ORDER BY due_at ASC, id ASC
            LIMIT ?;
            """,
            (upper.isoformat(), max(1, int(limit))),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def find_reminders(
    query: str,
    *,
    include_done: bool = False,
    recurring_only: bool = False,
    limit: int = 5,
) -> list[dict[str, Any]]:
    text = str(query or "").strip().lower()
    if not text:
        raise ValueError("Reminder search text cannot be empty.")

    clauses = ["(LOWER(title) LIKE ? OR LOWER(notes) LIKE ?)"]
    params: list[object] = [f"%{text}%", f"%{text}%"]
    if not include_done:
        clauses.append("status = 'pending'")
    if recurring_only:
        clauses.append("recurrence != 'once'")

    conn = _connect()
    with _lock, conn:
        rows = conn.execute(
            f"""
            SELECT * FROM reminders
            WHERE {' AND '.join(clauses)}
            ORDER BY due_at ASC, id ASC
            LIMIT ?;
            """,
            [*params, max(1, int(limit))],
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def update_reminder(
    reminder_id: int,
    *,
    title: str | None = None,
    notes: str | None = None,
    due_at: datetime | str | None = None,
    recurrence: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    current = get_reminder(reminder_id)
    updates: dict[str, object] = {}
    if title is not None:
        title_text = str(title).strip()
        if not title_text:
            raise ValueError("Reminder title cannot be empty.")
        updates["title"] = title_text
    if notes is not None:
        updates["notes"] = str(notes).strip()
    if due_at is not None:
        updates["due_at"] = _normalize_datetime(due_at).isoformat()
    if recurrence is not None:
        updates["recurrence"] = normalize_recurrence(recurrence)
    if status is not None:
        updates["status"] = normalize_status(status)
    if not updates:
        return current

    updates["updated_at"] = _now_iso()
    if "status" in updates and updates["status"] != "done" and current.get("completed_at"):
        updates["completed_at"] = None

    assignments = ", ".join(f"{column} = ?" for column in updates)
    params = [*updates.values(), int(reminder_id)]
    conn = _connect()
    with _lock, conn:
        conn.execute(f"UPDATE reminders SET {assignments} WHERE id = ?;", params)
    return get_reminder(reminder_id)


def delete_reminder(reminder_id: int) -> dict[str, Any]:
    current = get_reminder(reminder_id)
    conn = _connect()
    with _lock, conn:
        conn.execute("DELETE FROM reminders WHERE id = ?;", (int(reminder_id),))
    return current


def complete_reminder(reminder_id: int) -> dict[str, Any]:
    current = get_reminder(reminder_id)
    if current["status"] != "pending":
        raise ValueError(f"Reminder `{current['title']}` is not currently pending.")

    now = datetime.now().astimezone()
    recurrence = str(current["recurrence"])
    conn = _connect()
    with _lock, conn:
        if recurrence == "once":
            conn.execute(
                """
                UPDATE reminders
                SET status = 'done', completed_at = ?, updated_at = ?
                WHERE id = ?;
                """,
                (now.isoformat(), now.isoformat(), int(reminder_id)),
            )
        else:
            next_due = advance_due_at(current["due_at"], recurrence, now=now)
            conn.execute(
                """
                UPDATE reminders
                SET due_at = ?, completed_at = ?, updated_at = ?, status = 'pending'
                WHERE id = ?;
                """,
                (next_due.isoformat(), now.isoformat(), now.isoformat(), int(reminder_id)),
            )
    return get_reminder(reminder_id)


def advance_due_at(due_at: datetime | str, recurrence: str, *, now: datetime | None = None) -> datetime:
    recurrence_value = normalize_recurrence(recurrence)
    current = _normalize_datetime(due_at)
    threshold = now.astimezone() if now is not None else datetime.now().astimezone()

    if recurrence_value == "once":
        return current

    next_due = current
    while next_due <= threshold:
        if recurrence_value == "daily":
            next_due += timedelta(days=1)
        elif recurrence_value == "weekday":
            next_due += timedelta(days=1)
            while next_due.weekday() >= 5:
                next_due += timedelta(days=1)
        elif recurrence_value == "weekly":
            next_due += timedelta(days=7)
    return next_due


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    due = _normalize_datetime(str(data["due_at"]))
    data["due_at"] = due.isoformat()
    data["is_routine"] = str(data.get("recurrence") or "once") != "once"
    data["is_overdue"] = str(data.get("status") or "pending") == "pending" and due < datetime.now().astimezone()
    return data


def _normalize_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value or "").strip()
        if not raw:
            raise ValueError("Reminder due time cannot be empty.")
        normalized = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(f"Could not parse reminder date/time '{value}'.") from exc

    if parsed.tzinfo is None:
        local_tz = datetime.now().astimezone().tzinfo
        default_tz = local_tz if local_tz is not None else time.min.tzinfo
        parsed = parsed.replace(tzinfo=default_tz)
    return parsed.astimezone()


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()
