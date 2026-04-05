from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from backend.ai_engine import build_jarvin_config, generate_reply

_BRIEF_HINTS = (
    "morning brief",
    "daily brief",
    "today's brief",
    "todays brief",
    "rundown",
    "brief me",
    "sum up my day",
    "summarize my day",
    "what's my day look like",
    "what does my day look like",
    "what do i have going on today",
)
_FOLLOW_UP_HINTS = (
    "how about tomorrow",
    "what about tomorrow",
    "how about today",
    "what about today",
    "and tomorrow",
    "for tomorrow",
)


@dataclass(frozen=True)
class BriefPlan:
    is_brief_request: bool
    day_offset: int = 0
    location_hint: str | None = None


@dataclass(frozen=True)
class BriefConversationContext:
    day_offset: int = 0
    location_hint: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=15))


_brief_context: dict[str, BriefConversationContext] = {}


def maybe_plan_brief_request(text: str, *, conversation_id: int | None = None) -> BriefPlan | None:
    message = (text or "").strip()
    if not message:
        return None

    context = get_brief_context(conversation_id)
    heuristic = _heuristic_plan(message, context=context)
    if heuristic is not None:
        return heuristic

    if not _looks_brief_related(message, context=context):
        return None

    plan = _llm_plan_brief_request(message, context=context)
    if not plan.is_brief_request:
        return None
    return _resolve_context(plan, context=context)


def get_brief_context(conversation_id: int | None) -> BriefConversationContext | None:
    key = _context_key(conversation_id)
    context = _brief_context.get(key)
    if context is None:
        return None
    if context.expires_at <= datetime.now(timezone.utc):
        _brief_context.pop(key, None)
        return None
    return context


def remember_brief_context(conversation_id: int | None, *, day_offset: int, location_hint: str | None) -> None:
    _brief_context[_context_key(conversation_id)] = BriefConversationContext(
        day_offset=day_offset,
        location_hint=location_hint,
    )


def clear_brief_context(conversation_id: int | None) -> None:
    _brief_context.pop(_context_key(conversation_id), None)


def _context_key(conversation_id: int | None) -> str:
    return str(conversation_id) if conversation_id is not None else "__default__"


def _heuristic_plan(message: str, *, context: BriefConversationContext | None) -> BriefPlan | None:
    lower = message.lower()

    if any(hint in lower for hint in _FOLLOW_UP_HINTS) and context is not None:
        day_offset = 1 if "tomorrow" in lower else 0
        return BriefPlan(is_brief_request=True, day_offset=day_offset, location_hint=context.location_hint)

    if any(hint in lower for hint in _BRIEF_HINTS):
        return BriefPlan(
            is_brief_request=True,
            day_offset=_infer_day_offset(lower),
            location_hint=_extract_location(message),
        )

    return None


def _looks_brief_related(message: str, *, context: BriefConversationContext | None) -> bool:
    lower = message.lower()
    if any(hint in lower for hint in _BRIEF_HINTS):
        return True
    if context is None:
        return False
    return any(hint in lower for hint in _FOLLOW_UP_HINTS)


def _llm_plan_brief_request(message: str, *, context: BriefConversationContext | None) -> BriefPlan:
    system = (
        "You extract daily-brief arguments for Jarvin. "
        "Return JSON only with keys: is_brief_request (boolean), day_offset (integer), location_hint (string|null). "
        "Use day_offset 0 for today, 1 for tomorrow. "
        "Treat requests like 'give me the rundown for today', 'brief me on my day', or 'what does my day look like' as brief requests. "
        "If the user is following up with 'how about tomorrow', keep the same location from context if none is mentioned. "
        "Do not answer the brief request itself."
    )
    prompt = (
        "Recent brief context:\n"
        f"day_offset={context.day_offset if context else 0}\n"
        f"location_hint={context.location_hint if context else ''}\n\n"
        f"User message:\n{message}"
    )
    cfg_obj = build_jarvin_config(
        mode="agent_strong",
        system_instructions=system,
        temperature=0.1,
        max_tokens=160,
    )
    raw = generate_reply(prompt, cfg=cfg_obj, context=None)
    data = _parse_json_object(raw)
    return BriefPlan(
        is_brief_request=bool(data.get("is_brief_request")),
        day_offset=_coerce_day_offset(data.get("day_offset")),
        location_hint=_clean_text(data.get("location_hint")),
    )


def _resolve_context(plan: BriefPlan, *, context: BriefConversationContext | None) -> BriefPlan:
    if context is None:
        return plan
    return BriefPlan(
        is_brief_request=plan.is_brief_request,
        day_offset=plan.day_offset,
        location_hint=plan.location_hint or context.location_hint,
    )


def _infer_day_offset(lower: str) -> int:
    if "tomorrow" in lower:
        return 1
    return 0


def _extract_location(message: str) -> str | None:
    match = re.search(r"\bin\s+([A-Za-z0-9 .,'-]+)$", message)
    if not match:
        match = re.search(r"\bfor\s+([A-Za-z0-9 .,'-]+)$", message)
        if not match:
            return None
    return _clean_text(match.group(1))


def _coerce_day_offset(value: object) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, min(parsed, 1))


def _parse_json_object(text: str) -> dict[str, object]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}


def _clean_text(value: object) -> str | None:
    cleaned = str(value or "").strip().rstrip("?.!,")
    return cleaned or None
