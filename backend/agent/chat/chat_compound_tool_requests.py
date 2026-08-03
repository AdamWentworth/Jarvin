from __future__ import annotations

import json
import re
from dataclasses import dataclass

from backend.ai_engine import build_jarvin_config, generate_reply
from backend.agent.calendar.calendar_request_nlu import extract_date_hint

_SUPPORTED_DOMAINS = {"reminder", "calendar"}
_COMPOUND_SEPARATORS = (" and ", " then ", " also ", " after that ", " plus ")
_ACTION_HINTS = (
    "remind",
    "reminder",
    "delete",
    "remove",
    "cancel",
    "create",
    "add",
    "schedule",
    "make",
    "move",
    "reschedule",
    "rename",
    "update",
)
_BLOCKING_REPLY_HINTS = (
    "reply `yes`",
    "reply `approve`",
    "what time should i",
    "tell me which",
    "tell me when",
    "please be more specific",
    "i found multiple matching",
)


@dataclass(frozen=True)
class CompoundToolStep:
    domain: str
    prompt: str


@dataclass(frozen=True)
class CompoundToolPlan:
    is_compound_request: bool
    steps: tuple[CompoundToolStep, ...] = ()


def maybe_plan_compound_tool_request(text: str) -> CompoundToolPlan | None:
    message = str(text or "").strip()
    if not _looks_like_compound_candidate(message):
        return None

    system = (
        "You decompose Jarvin assistant requests into separate local tool steps. "
        "Return JSON only with keys: is_compound_request (boolean) and steps (array). "
        "Each step must be an object with keys domain and prompt. "
        "Supported domains are reminder and calendar only. "
        "Use is_compound_request=true only when the user clearly asked for two or more separate actions. "
        "Keep each prompt self-contained so Jarvin can execute it directly. "
        "If the request is really one action, return is_compound_request=false and steps=[]. "
        "Do not answer the user. Do not invent extra steps."
    )
    prompt = (
        "Decompose this request if needed.\n\n"
        f"User message:\n{message}"
    )
    cfg_obj = build_jarvin_config(
        mode="agent_strong",
        system_instructions=system,
        temperature=0.1,
        max_tokens=220,
    )
    raw = generate_reply(prompt, cfg=cfg_obj, context=None)
    data = _parse_json_object(raw)

    is_compound = bool(data.get("is_compound_request"))
    raw_steps = data.get("steps")
    if not isinstance(raw_steps, list):
        raw_steps = []

    steps: list[CompoundToolStep] = []
    for item in raw_steps[:3]:
        if not isinstance(item, dict):
            continue
        domain = str(item.get("domain") or "").strip().lower()
        step_prompt = _clean_text(item.get("prompt"))
        if domain not in _SUPPORTED_DOMAINS or not step_prompt:
            continue
        steps.append(CompoundToolStep(domain=domain, prompt=step_prompt))

    if not is_compound or len(steps) < 2:
        return None
    return CompoundToolPlan(is_compound_request=True, steps=tuple(steps))


def maybe_compound_tool_response_impl(
    text: str,
    *,
    conversation_id,
    ToolChatResponse,
    maybe_plan_compound_tool_request,
    maybe_handle_reminder_request,
    maybe_calendar_tool_response,
):
    plan = maybe_plan_compound_tool_request(text)
    if plan is None or not plan.is_compound_request or len(plan.steps) < 2:
        return None

    return execute_compound_tool_steps(
        plan.steps,
        source_text=text,
        conversation_id=conversation_id,
        ToolChatResponse=ToolChatResponse,
        maybe_handle_reminder_request=maybe_handle_reminder_request,
        maybe_calendar_tool_response=maybe_calendar_tool_response,
    )


def execute_compound_tool_steps(
    steps,
    *,
    source_text=None,
    conversation_id,
    ToolChatResponse,
    maybe_handle_reminder_request,
    maybe_calendar_tool_response,
):
    normalized_steps = _normalize_compound_steps(steps, source_text=source_text)
    replies: list[str] = []
    active_domain: str | None = None
    blocking_response = None

    for step in normalized_steps:
        response = _execute_compound_step(
            step,
            conversation_id=conversation_id,
            ToolChatResponse=ToolChatResponse,
            maybe_handle_reminder_request=maybe_handle_reminder_request,
            maybe_calendar_tool_response=maybe_calendar_tool_response,
        )
        if response is None or not response.handled or not response.reply:
            continue
        replies.append(response.reply.strip())
        active_domain = response.active_domain or step.domain
        if _is_blocking_response(response):
            blocking_response = response
            break

    if not replies:
        return None

    combined_reply = "\n\n".join(replies)
    if blocking_response is not None:
        return ToolChatResponse(
            handled=True,
            reply=combined_reply,
            tool_kind=blocking_response.tool_kind,
            tool_payload=blocking_response.tool_payload,
            active_domain=active_domain,
            persist_assistant_turn=blocking_response.persist_assistant_turn,
        )

    return ToolChatResponse(
        handled=True,
        reply=combined_reply,
        active_domain=active_domain,
    )


def _execute_compound_step(
    step: CompoundToolStep,
    *,
    conversation_id,
    ToolChatResponse,
    maybe_handle_reminder_request,
    maybe_calendar_tool_response,
):
    if step.domain == "reminder":
        reply = maybe_handle_reminder_request(step.prompt, conversation_id=conversation_id)
        if reply is None:
            return None
        return ToolChatResponse(handled=True, reply=reply, active_domain="reminder")

    if step.domain == "calendar":
        return maybe_calendar_tool_response(step.prompt, conversation_id=conversation_id)

    return None


def _normalize_compound_steps(steps, *, source_text) -> tuple[CompoundToolStep, ...]:
    shared_date_hint = extract_date_hint(str(source_text or ""))
    normalized: list[CompoundToolStep] = []
    for step in steps:
        if step.domain != "reminder" or not shared_date_hint or extract_date_hint(step.prompt):
            normalized.append(step)
            continue
        prompt = re.sub(
            r"\b(reminder)\s+(at\b)",
            rf"\1 {shared_date_hint} \2",
            step.prompt,
            count=1,
            flags=re.IGNORECASE,
        )
        if prompt == step.prompt:
            prompt = re.sub(
                r"\b(reminder)\b",
                rf"\1 {shared_date_hint}",
                step.prompt,
                count=1,
                flags=re.IGNORECASE,
            )
        normalized.append(CompoundToolStep(domain=step.domain, prompt=prompt))
    return tuple(normalized)


def _looks_like_compound_candidate(message: str) -> bool:
    lower = str(message or "").strip().lower()
    if not lower:
        return False
    if not any(separator in lower for separator in _COMPOUND_SEPARATORS):
        return False
    action_hits = sum(1 for hint in _ACTION_HINTS if hint in lower)
    if action_hits < 2:
        return False
    return any(token in lower for token in ("remind", "reminder", "calendar", "appointment", "meeting", "event"))


def _is_blocking_response(response) -> bool:
    if getattr(response, "tool_kind", None):
        return True
    lower = str(getattr(response, "reply", "") or "").strip().lower()
    return any(hint in lower for hint in _BLOCKING_REPLY_HINTS)


def _parse_json_object(text: str) -> dict[str, object]:
    body = str(text or "").strip()
    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", body, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}


def _clean_text(value: object) -> str | None:
    cleaned = str(value or "").strip().rstrip("?.!,")
    return cleaned or None
