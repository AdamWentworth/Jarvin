from __future__ import annotations

from pathlib import Path
import json
import sqlite3
import threading
from typing import Any

import config as cfg

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
            CREATE TABLE IF NOT EXISTS agent_action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                event_kind TEXT NOT NULL,
                action_kind TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                access_mode TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                command TEXT,
                path TEXT,
                content_preview TEXT,
                detail TEXT
            );

            CREATE INDEX IF NOT EXISTS ix_agent_action_log_created_at
            ON agent_action_log(created_at DESC, id DESC);

            CREATE INDEX IF NOT EXISTS ix_agent_action_log_conversation
            ON agent_action_log(conversation_id, id DESC);
            """
        )
        _ensure_column(conn, "agent_action_log", "client_session_id", "TEXT")
        _ensure_column(conn, "agent_action_log", "trust_scope", "TEXT")
        _ensure_column(conn, "agent_action_log", "working_directory", "TEXT")
        _ensure_column(conn, "agent_action_log", "argv_json", "TEXT")
        _ensure_column(conn, "agent_action_log", "diff_preview", "TEXT")


def _reset_for_tests() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
    _conn = None


def log_agent_action_event(
    *,
    conversation_id: int | None,
    event_kind: str,
    action_kind: str,
    risk_level: str,
    access_mode: str,
    title: str,
    summary: str,
    command: str | None = None,
    path: str | None = None,
    content_preview: str | None = None,
    detail: str | None = None,
    client_session_id: str | None = None,
    trust_scope: str | None = None,
    working_directory: str | None = None,
    argv: list[str] | None = None,
    diff_preview: str | None = None,
) -> dict[str, Any]:
    conn = _connect()
    with _lock, conn:
        cur = conn.execute(
            """
            INSERT INTO agent_action_log (
                conversation_id,
                event_kind,
                action_kind,
                risk_level,
                access_mode,
                title,
                summary,
                command,
                path,
                content_preview,
                detail,
                client_session_id,
                trust_scope,
                working_directory,
                argv_json,
                diff_preview
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                conversation_id,
                str(event_kind or "").strip(),
                str(action_kind or "").strip(),
                str(risk_level or "").strip(),
                str(access_mode or "").strip(),
                str(title or "").strip(),
                str(summary or "").strip(),
                _clean_optional(command),
                _clean_optional(path),
                _clean_preview(content_preview),
                _clean_optional(detail),
                _clean_optional(client_session_id),
                _clean_optional(trust_scope),
                _clean_optional(working_directory),
                _clean_argv(argv),
                _clean_preview(diff_preview),
            ),
        )
        event_id = int(cur.lastrowid)
    return get_agent_action_event(event_id)


def get_agent_action_event(event_id: int) -> dict[str, Any]:
    conn = _connect()
    with _lock, conn:
        row = conn.execute("SELECT * FROM agent_action_log WHERE id = ?;", (int(event_id),)).fetchone()
    if row is None:
        raise ValueError(f"Agent action event {event_id} does not exist.")
    return _coerce_row(row)


def list_agent_action_events(*, limit: int = 50, conversation_id: int | None = None) -> list[dict[str, Any]]:
    conn = _connect()
    params: list[object] = []
    where = ""
    if conversation_id is not None:
        where = "WHERE conversation_id = ?"
        params.append(int(conversation_id))

    params.append(max(1, min(int(limit), 200)))
    with _lock, conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM agent_action_log
            {where}
            ORDER BY id DESC
            LIMIT ?;
            """,
            params,
        ).fetchall()
    return [_coerce_row(row) for row in rows]


def _clean_optional(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _clean_preview(value: str | None) -> str | None:
    preview = str(value or "").replace("\r\n", "\n").strip()
    if not preview:
        return None
    if len(preview) > 240:
        preview = preview[:237].rstrip() + "..."
    return preview


def _clean_argv(argv: list[str] | None) -> str | None:
    if not argv:
        return None
    return json.dumps([str(item) for item in argv], ensure_ascii=True)


def _coerce_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    raw_argv = item.pop("argv_json", None)
    item["argv"] = None
    if raw_argv:
        try:
            decoded = json.loads(raw_argv)
            if isinstance(decoded, list):
                item["argv"] = [str(value) for value in decoded]
        except Exception:
            item["argv"] = None
    return item


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
    existing = {
        str(row["name"])
        for row in conn.execute(f"PRAGMA table_info({table});").fetchall()
    }
    if column in existing:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type};")
