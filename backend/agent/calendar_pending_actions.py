from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class PendingCalendarAction:
    action: str
    event_id: str
    title: str
    starts_at: str
    new_start_iso: str | None = None
    new_end_iso: str | None = None
    new_title: str | None = None
    new_location: str | None = None
    new_description: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=10))


_pending_actions: dict[str, PendingCalendarAction] = {}


def set_pending_calendar_action(conversation_id: int | None, action: PendingCalendarAction) -> None:
    _pending_actions[_key(conversation_id)] = action


def get_pending_calendar_action(conversation_id: int | None) -> PendingCalendarAction | None:
    key = _key(conversation_id)
    action = _pending_actions.get(key)
    if action is None:
        return None
    if action.expires_at <= datetime.now(timezone.utc):
        _pending_actions.pop(key, None)
        return None
    return action


def clear_pending_calendar_action(conversation_id: int | None) -> None:
    _pending_actions.pop(_key(conversation_id), None)


def _key(conversation_id: int | None) -> str:
    return str(conversation_id) if conversation_id is not None else "__default__"
