# memory/conversation.py
from __future__ import annotations

from pathlib import Path
import sqlite3
import threading
from typing import Any, Dict, List, Tuple, Optional

import config as cfg

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is not None:
        return _conn

    settings = cfg.settings

    # 1. Resolve db_path robustly
    db_path = getattr(settings, "db_path", None)
    if db_path is not None:
        db_path = Path(db_path)
    else:
        data_dir = getattr(settings, "data_dir", None)
        db_filename = getattr(settings, "db_filename", None)

        if data_dir is None or db_filename is None:
            raise RuntimeError(
                "config.settings must provide either 'db_path' or both 'data_dir' and 'db_filename'."
            )

        data_dir = Path(data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = data_dir / db_filename

    _conn = sqlite3.connect(str(db_path), check_same_thread=False)
    _conn.row_factory = sqlite3.Row

    # 2. Optional pragmas
    try:
        if getattr(settings, "db_wal", False):
            _conn.execute("PRAGMA journal_mode=WAL;")
        _conn.execute("PRAGMA synchronous=NORMAL;")
        _conn.execute("PRAGMA foreign_keys=ON;")
    except Exception:
        # Fail-soft on pragma tuning
        pass

    _migrate(_conn)
    return _conn


def _column_exists(conn: sqlite3.Connection, table: str, col: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table});")
    return any(r["name"] == col for r in cur.fetchall())


def _migrate(conn: sqlite3.Connection) -> None:
    """
    Create/upgrade schema. Backfills a single-log DB into a first conversation.
    """
    with conn:
        # --- Base tables (old app already had these) ---
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT,
                goal TEXT,
                mood TEXT,
                communication_style TEXT,
                response_length TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL CHECK (role IN ('user','assistant')),
                message TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # --- New tables for multi-convo ---
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                closed_at DATETIME
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )

        # Add FK column if missing
        if not _column_exists(conn, "conversation_history", "conversation_id"):
            conn.execute(
                "ALTER TABLE conversation_history ADD COLUMN conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE;"
            )

        # Helpful indexes
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_conv_hist_conv_id ON conversation_history(conversation_id, id);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_conv_hist_created_at ON conversation_history(created_at);"
        )

        # Bootstrap: ensure at least one conversation exists
        cur = conn.execute("SELECT COUNT(*) AS n FROM conversations;").fetchone()
        if int(cur["n"]) == 0:
            # Create a default conversation
            conn.execute("INSERT INTO conversations (title) VALUES ('Conversation 1');")

        # Backfill any null conversation_id rows (older DBs)
        cur = conn.execute("SELECT id FROM conversations ORDER BY id ASC LIMIT 1;").fetchone()
        default_cid = int(cur["id"])

        conn.execute(
            "UPDATE conversation_history SET conversation_id = ? WHERE conversation_id IS NULL;",
            (default_cid,),
        )

        # Ensure there's an active conversation set
        cur = conn.execute("SELECT value FROM app_state WHERE key = 'active_conversation_id';").fetchone()
        if not cur:
            conn.execute(
                "INSERT OR REPLACE INTO app_state (key, value) VALUES ('active_conversation_id', ?);",
                (str(default_cid),),
            )


def _generate_default_title(conn: sqlite3.Connection) -> str:
    """
    Generate a unique default title:

      New conversation
      New conversation (1)
      New conversation (2)
      ...

    Only used when no explicit title is provided.
    """
    base = "New conversation"
    rows = conn.execute("SELECT title FROM conversations;").fetchall()
    existing = {(r["title"] or "").strip() for r in rows}

    if base not in existing:
        return base

    i = 1
    while True:
        candidate = f"{base} ({i})"
        if candidate not in existing:
            return candidate
        i += 1


# ---------- Active conversation helpers ----------

def _get_active_conversation_id(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT value FROM app_state WHERE key = 'active_conversation_id';").fetchone()
    if not row or not row["value"]:
        # Fallback: pick the oldest convo and set it active
        cur = conn.execute("SELECT id FROM conversations ORDER BY id ASC LIMIT 1;").fetchone()
        cid = int(cur["id"])
        conn.execute(
            "INSERT OR REPLACE INTO app_state (key, value) VALUES ('active_conversation_id', ?);",
            (str(cid),),
        )
        return cid
    return int(row["value"])


def _set_active_conversation_id(conn: sqlite3.Connection, conversation_id: int) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO app_state (key, value) VALUES ('active_conversation_id', ?);",
        (str(int(conversation_id)),),
    )


# ---------- Public multi-conversation API ----------

def list_conversations() -> List[Dict[str, Any]]:
    """
    Returns [{id, title, created_at, messages}, ...] newest first.
    """
    conn = _connect()
    with _lock, conn:
        rows = conn.execute(
            """
            SELECT c.id, c.title, c.created_at,
                   (SELECT COUNT(1) FROM conversation_history h WHERE h.conversation_id = c.id) AS messages
            FROM conversations c
            ORDER BY c.id DESC;
            """
        ).fetchall()
        return [dict(r) for r in rows]


def new_conversation(title: str | None = None, *, activate: bool = True) -> int:
    """
    Create a new conversation. If activate=True, makes it the active one.
    Returns the new conversation id.

    If `title` is empty/None, a unique default is generated:
      New conversation
      New conversation (1)
      New conversation (2)
      ...
    """
    conn = _connect()
    raw_title = (title or "").strip()
    with _lock, conn:
        if raw_title:
            final_title = raw_title
        else:
            final_title = _generate_default_title(conn)

        cur = conn.execute("INSERT INTO conversations (title) VALUES (?);", (final_title,))
        cid = int(cur.lastrowid)
        if activate:
            _set_active_conversation_id(conn, cid)
        return cid


def rename_conversation(conversation_id: int, title: str) -> None:
    conn = _connect()
    with _lock, conn:
        conn.execute("UPDATE conversations SET title = ? WHERE id = ?;", (title.strip(), int(conversation_id)))


def delete_conversation(conversation_id: int) -> None:
    """
    Deletes the conversation and its messages. If it was active,
    switches active to the most recent remaining conversation (or creates one).
    """
    conn = _connect()
    with _lock, conn:
        # Delete
        conn.execute("DELETE FROM conversations WHERE id = ?;", (int(conversation_id),))
        # Choose a new active if needed
        cur = conn.execute("SELECT value FROM app_state WHERE key = 'active_conversation_id';").fetchone()
        active = int(cur["value"]) if cur and cur["value"] else None
        if active == int(conversation_id):
            nxt = conn.execute("SELECT id FROM conversations ORDER BY id DESC LIMIT 1;").fetchone()
            if nxt:
                _set_active_conversation_id(conn, int(nxt["id"]))
            else:
                # Create a fresh one
                nid = new_conversation("Conversation 1", activate=False)
                _set_active_conversation_id(conn, nid)


def get_active_conversation_id() -> int:
    conn = _connect()
    with _lock:
        return _get_active_conversation_id(conn)


def set_active_conversation(conversation_id: int) -> None:
    conn = _connect()
    with _lock, conn:
        # Validate exists
        row = conn.execute("SELECT 1 FROM conversations WHERE id = ?;", (int(conversation_id),)).fetchone()
        if not row:
            raise ValueError(f"Conversation {conversation_id} does not exist.")
        _set_active_conversation_id(conn, int(conversation_id))


# ---------- Backward-compatible API (now scoped to ACTIVE conversation) ----------

def get_conversation_history(conversation_id: Optional[int] = None) -> List[Tuple[str, str]]:
    """
    Return [(role, message), ...] ordered by insertion for the given conversation
    (or the active one if not provided).
    """
    conn = _connect()
    with _lock:
        cid = int(conversation_id or _get_active_conversation_id(conn))
        cur = conn.execute(
            "SELECT role, message FROM conversation_history WHERE conversation_id = ? ORDER BY id ASC;",
            (cid,),
        )
        return [(row["role"], row["message"]) for row in cur.fetchall()]


def set_conversation_history(history: List[Tuple[str, str]], conversation_id: Optional[int] = None) -> None:
    """
    Replace the entire history for the given (or active) conversation.
    """
    conn = _connect()
    with _lock, conn:
        cid = int(conversation_id or _get_active_conversation_id(conn))
        conn.execute("DELETE FROM conversation_history WHERE conversation_id = ?;", (cid,))
        if history:
            conn.executemany(
                "INSERT INTO conversation_history (role, message, conversation_id) VALUES (?, ?, ?);",
                [(r, m, cid) for (r, m) in history],
            )


def append_turn(role: str, message: str, conversation_id: Optional[int] = None) -> None:
    conn = _connect()
    with _lock, conn:
        cid = int(conversation_id or _get_active_conversation_id(conn))
        conn.execute(
            "INSERT INTO conversation_history (role, message, conversation_id) VALUES (?, ?, ?);",
            (role, message, cid),
        )


def clear_conversation(conversation_id: Optional[int] = None) -> None:
    conn = _connect()
    with _lock, conn:
        cid = int(conversation_id or _get_active_conversation_id(conn))
        conn.execute("DELETE FROM conversation_history WHERE conversation_id = ?;", (cid,))


# ---------- Profile (unchanged) ----------

def get_user_profile() -> Dict[str, Any]:
    """
    Return a dict of saved profile fields; empty values if not set yet.
    """
    conn = _connect()
    with _lock:
        cur = conn.execute("SELECT * FROM user_profile WHERE id = 1;")
        row = cur.fetchone()
        if not row:
            return {}
        return {
            "name": row["name"],
            "goal": row["goal"],
            "mood": row["mood"],
            "communication_style": row["communication_style"],
            "response_length": row["response_length"],
        }


def set_user_profile(profile: Dict[str, Any]) -> None:
    """
    Upsert id=1 with given fields.
    """
    conn = _connect()
    fields = {
        "name": profile.get("name"),
        "goal": profile.get("goal"),
        "mood": profile.get("mood"),
        "communication_style": profile.get("communication_style"),
        "response_length": profile.get("response_length"),
    }
    with _lock, conn:
        conn.execute(
            """
            INSERT INTO user_profile (id, name, goal, mood, communication_style, response_length, updated_at)
            VALUES (1, :name, :goal, :mood, :communication_style, :response_length, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                goal=excluded.goal,
                mood=excluded.mood,
                communication_style=excluded.communication_style,
                response_length=excluded.response_length,
                updated_at=CURRENT_TIMESTAMP;
            """,
            fields,
        )
