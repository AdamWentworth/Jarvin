from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from backend.ai_engine import build_jarvin_config, generate_reply

_RESEARCH_HINTS = (
    "research",
    "look into",
    "dig into",
    "what does the web say",
    "find out about",
    "read up on",
    "look up",
    "search the web",
    "find information on",
)
_FOLLOW_UP_HINTS = (
    "what else did you find",
    "what else did you learn",
    "summarize that",
    "summarize what you found",
    "compare the sources",
    "compare those sources",
    "compare the top sources",
    "what did you find",
    "what did you learn",
)


@dataclass(frozen=True)
class ResearchPlan:
    is_research_request: bool
    action: str = "unknown"
    query: str | None = None


@dataclass(frozen=True)
class ResearchConversationContext:
    last_action: str = "web_search"
    last_query: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=15))


_research_context: dict[str, ResearchConversationContext] = {}


def maybe_plan_research_request(text: str, *, conversation_id: int | None = None) -> ResearchPlan | None:
    message = (text or "").strip()
    if not message:
        return None

    context = get_research_context(conversation_id)
    heuristic = _heuristic_plan(message, context=context)
    if heuristic is not None:
        return heuristic

    if not _looks_research_related(message, context=context):
        return None

    plan = _llm_plan_research_request(message, context=context)
    if not plan.is_research_request:
        return None
    return _resolve_context(plan, context=context)


def get_research_context(conversation_id: int | None) -> ResearchConversationContext | None:
    key = _context_key(conversation_id)
    context = _research_context.get(key)
    if context is None:
        return None
    if context.expires_at <= datetime.now(timezone.utc):
        _research_context.pop(key, None)
        return None
    return context


def remember_research_context(conversation_id: int | None, *, action: str, query: str | None) -> None:
    _research_context[_context_key(conversation_id)] = ResearchConversationContext(
        last_action=action or "web_search",
        last_query=query,
    )


def clear_research_context(conversation_id: int | None) -> None:
    _research_context.pop(_context_key(conversation_id), None)


def _context_key(conversation_id: int | None) -> str:
    return str(conversation_id) if conversation_id is not None else "__default__"


def _heuristic_plan(message: str, *, context: ResearchConversationContext | None) -> ResearchPlan | None:
    lower = message.lower()

    if lower.startswith("google "):
        return ResearchPlan(is_research_request=True, action="google_search", query=_clean_query(message[7:]))
    if lower.startswith(("google this ", "google that ")):
        candidate = re.sub(r"^google\s+(?:this|that)\s+", "", message, flags=re.IGNORECASE)
        return ResearchPlan(is_research_request=True, action="google_search", query=_clean_query(candidate))

    if any(hint in lower for hint in _FOLLOW_UP_HINTS) and context and context.last_query:
        return ResearchPlan(is_research_request=True, action=context.last_action or "web_search", query=context.last_query)

    if any(hint in lower for hint in _RESEARCH_HINTS):
        query = _extract_research_query(message)
        if query:
            return ResearchPlan(is_research_request=True, action="web_search", query=query)

    return None


def _looks_research_related(message: str, *, context: ResearchConversationContext | None) -> bool:
    lower = message.lower()
    if lower.startswith("google "):
        return True
    if any(hint in lower for hint in _RESEARCH_HINTS):
        return True
    if context is None:
        return False
    return any(hint in lower for hint in _FOLLOW_UP_HINTS)


def _llm_plan_research_request(message: str, *, context: ResearchConversationContext | None) -> ResearchPlan:
    system = (
        "You extract web research tool arguments for Jarvin. "
        "Return JSON only with keys: is_research_request (boolean), action (string), query (string|null). "
        "Valid actions are web_search, google_search, unknown. "
        "Choose google_search only if the user explicitly asks for Google. "
        "For requests like 'research this for me', 'look into this', 'what does the web say about X', or "
        "'compare sources on X', choose web_search and extract the query. "
        "If the user is following up on a prior research turn and does not repeat the topic, query may be null. "
        "Do not answer the research question itself."
    )
    prompt = (
        "Recent research context:\n"
        f"last_action={context.last_action if context else ''}\n"
        f"last_query={context.last_query if context else ''}\n\n"
        f"User message:\n{message}"
    )
    cfg_obj = build_jarvin_config(
        mode="agent_strong",
        system_instructions=system,
        temperature=0.1,
        max_tokens=180,
    )
    raw = generate_reply(prompt, cfg=cfg_obj, context=None)
    data = _parse_json_object(raw)
    return ResearchPlan(
        is_research_request=bool(data.get("is_research_request")),
        action=str(data.get("action") or "unknown").strip().lower(),
        query=_clean_query(data.get("query")),
    )


def _resolve_context(plan: ResearchPlan, *, context: ResearchConversationContext | None) -> ResearchPlan:
    if context is None:
        return plan
    query = plan.query or context.last_query
    action = plan.action if plan.action != "unknown" else context.last_action
    return ResearchPlan(
        is_research_request=plan.is_research_request,
        action=action,
        query=query,
    )


def _extract_research_query(message: str) -> str | None:
    candidate = re.sub(
        r"(?:(?:can you|could you|please)\s+)?(?:research|look into|dig into|look up|search the web(?:\s+for)?|find information on|find out about|read up on)\s+",
        "",
        message,
        flags=re.IGNORECASE,
    )
    candidate = re.sub(r"^(?:what does the web say about)\s+", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"\s+(?:for me|and summarize.*|and tell me what you find|and let me know what you find)$", "", candidate, flags=re.IGNORECASE)
    cleaned = _clean_query(candidate)
    return cleaned or None


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


def _clean_query(value: object) -> str | None:
    cleaned = str(value or "").strip().rstrip("?.!,")
    return cleaned or None
