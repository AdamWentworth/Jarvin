from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class OrganizerConversationContext:
    last_action: str = "overview"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=15))


_organizer_context: dict[str, OrganizerConversationContext] = {}


def get_organizer_context(conversation_id: int | None) -> OrganizerConversationContext | None:
    key = _key(conversation_id)
    context = _organizer_context.get(key)
    if context is None:
        return None
    if context.expires_at <= datetime.now(timezone.utc):
        _organizer_context.pop(key, None)
        return None
    return context


def remember_organizer_context(conversation_id: int | None, *, action: str) -> None:
    _organizer_context[_key(conversation_id)] = OrganizerConversationContext(last_action=action or "overview")


def clear_organizer_context(conversation_id: int | None) -> None:
    _organizer_context.pop(_key(conversation_id), None)


def _key(conversation_id: int | None) -> str:
    return str(conversation_id) if conversation_id is not None else "__default__"
