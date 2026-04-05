from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class ActiveFollowUpContext:
    domain: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=15))


_active_follow_up_context: dict[str, ActiveFollowUpContext] = {}


def get_active_follow_up_domain(conversation_id: int | None) -> str | None:
    key = _context_key(conversation_id)
    context = _active_follow_up_context.get(key)
    if context is None:
        return None
    if context.expires_at <= datetime.now(timezone.utc):
        _active_follow_up_context.pop(key, None)
        return None
    return context.domain


def remember_active_follow_up_domain(conversation_id: int | None, domain: str | None) -> None:
    cleaned = str(domain or "").strip().lower()
    if not cleaned:
        return
    _active_follow_up_context[_context_key(conversation_id)] = ActiveFollowUpContext(domain=cleaned)


def clear_active_follow_up_domain(conversation_id: int | None) -> None:
    _active_follow_up_context.pop(_context_key(conversation_id), None)


def _context_key(conversation_id: int | None) -> str:
    return str(conversation_id) if conversation_id is not None else "__default__"
