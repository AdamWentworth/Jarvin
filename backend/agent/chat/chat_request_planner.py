from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from backend.ai_engine import build_jarvin_config, generate_reply

log = logging.getLogger("jarvin.agent.request_planner")

_SUPPORTED_DOMAINS = {
    "organizer",
    "reminder",
    "calendar",
    "weather",
    "brief",
    "workspace",
    "research",
    "compound",
    "none",
    "unknown",
}
_SUPPORTED_CONFIDENCE = {"high", "medium", "low"}
_ORGANIZER_OVERVIEW_HINTS = ("show", "list", "output", "overview", "current", "what do i have")
_ORGANIZER_CLEANUP_HINTS = ("delete all", "remove all", "clear all", "start over", "clean slate", "everything")


@dataclass(frozen=True)
class PlannedToolStep:
    domain: str
    prompt: str


@dataclass(frozen=True)
class PlannedToolRoute:
    is_tool_request: bool
    domain: str = "unknown"
    normalized_request: str | None = None
    confidence: str = "low"
    reason: str | None = None
    steps: tuple[PlannedToolStep, ...] = ()


def maybe_plan_tool_request_route(
    text: str,
    *,
    active_domain: str | None = None,
) -> PlannedToolRoute | None:
    message = str(text or "").strip()
    if not message or message.lower().startswith("/tool"):
        return None

    cfg_obj = build_jarvin_config(
        mode="agent_strong",
        system_instructions=_planner_system_prompt(),
        temperature=0.1,
        max_tokens=320,
    )
    prompt = (
        f"Current active follow-up domain: {active_domain or '(none)'}\n\n"
        f"User message:\n{message}"
    )
    try:
        raw = generate_reply(prompt, cfg=cfg_obj, context=None)
    except Exception as exc:
        log.debug("Top-level tool planner failed: %s", exc)
        return None

    data = _parse_json_object(raw)
    if not data:
        return None

    is_tool_request = bool(data.get("is_tool_request"))
    domain = str(data.get("domain") or "unknown").strip().lower()
    confidence = str(data.get("confidence") or "low").strip().lower()
    normalized_request = _clean_text(data.get("normalized_request"))
    reason = _clean_text(data.get("reason"))
    steps = _coerce_steps(data.get("steps"))

    if domain not in _SUPPORTED_DOMAINS:
        domain = "unknown"
    if confidence not in _SUPPORTED_CONFIDENCE:
        confidence = "low"
    if not is_tool_request or domain in {"none", "unknown"}:
        return None
    if domain == "compound" and len(steps) < 2:
        return None

    plan = PlannedToolRoute(
        is_tool_request=True,
        domain=domain,
        normalized_request=normalized_request,
        confidence=confidence,
        reason=reason,
        steps=steps,
    )
    plan = _apply_route_overrides(message, plan)
    log.info(
        "Top-level request planner routed message. domain=%s confidence=%s normalized=%s steps=%d",
        plan.domain,
        plan.confidence,
        plan.normalized_request or "",
        len(plan.steps),
    )
    return plan


def _planner_system_prompt() -> str:
    return (
        "You are Jarvin's top-level tool router. "
        "Decide whether the user's message should go to a specific assistant tool domain or should fall back to normal chat. "
        "Return JSON only with keys: is_tool_request, domain, normalized_request, confidence, reason, steps. "
        "Valid domain values are organizer, reminder, calendar, weather, brief, workspace, research, compound, none, unknown. "
        "Valid confidence values are high, medium, low. "
        "Use organizer for combined calendar-plus-reminder overview or cleanup, such as listing everything, starting over, or deleting all current items. "
        "Also use organizer for bulk cleanup requests that target only one planning domain, such as 'delete all my calendar events' or 'clear all my reminders'. "
        "Use compound for two or more separate reminder/calendar actions in one user request. "
        "When domain=compound, include steps as an array of {domain, prompt} with only reminder or calendar domains. "
        "normalized_request should rewrite the user's meaning into a concise domain-specific instruction without changing intent. "
        "If the user is not clearly asking for a Jarvin tool or integration, return is_tool_request=false and domain=none. "
        "Do not answer the user. Do not produce markdown."
    )


def _coerce_steps(value: object) -> tuple[PlannedToolStep, ...]:
    if not isinstance(value, list):
        return ()
    steps: list[PlannedToolStep] = []
    for item in value[:4]:
        if not isinstance(item, dict):
            continue
        domain = str(item.get("domain") or "").strip().lower()
        prompt = _clean_text(item.get("prompt"))
        if domain not in {"reminder", "calendar"} or not prompt:
            continue
        steps.append(PlannedToolStep(domain=domain, prompt=prompt))
    return tuple(steps)


def _apply_route_overrides(message: str, plan: PlannedToolRoute) -> PlannedToolRoute:
    lower = str(message or "").strip().lower()
    if len(plan.steps) >= 2:
        return PlannedToolRoute(
            is_tool_request=plan.is_tool_request,
            domain="compound",
            normalized_request=plan.normalized_request,
            confidence=plan.confidence if plan.confidence != "low" else "medium",
            reason=plan.reason,
            steps=plan.steps,
        )

    mentions_reminders = any(token in lower for token in ("reminder", "reminders", "task", "tasks", "todo", "to-do"))
    mentions_calendar = any(token in lower for token in ("calendar", "event", "events", "appointment", "appointments", "meeting", "meetings"))
    has_overview_hint = any(token in lower for token in _ORGANIZER_OVERVIEW_HINTS)
    has_cleanup_hint = any(token in lower for token in _ORGANIZER_CLEANUP_HINTS)

    if mentions_reminders and mentions_calendar and (has_overview_hint or has_cleanup_hint):
        normalized = plan.normalized_request or (
            "show all my reminders and calendar events"
            if has_overview_hint and not has_cleanup_hint
            else "clean up my reminders and calendar events"
        )
        return PlannedToolRoute(
            is_tool_request=True,
            domain="organizer",
            normalized_request=normalized,
            confidence=plan.confidence if plan.confidence != "low" else "high",
            reason=plan.reason,
            steps=plan.steps,
        )

    if mentions_calendar and has_cleanup_hint and "all" in lower:
        normalized = plan.normalized_request or "delete all my calendar events"
        return PlannedToolRoute(
            is_tool_request=True,
            domain="organizer",
            normalized_request=normalized,
            confidence=plan.confidence if plan.confidence != "low" else "high",
            reason=plan.reason,
            steps=plan.steps,
        )

    if mentions_reminders and has_cleanup_hint and "all" in lower:
        normalized = plan.normalized_request or "delete all my reminders"
        return PlannedToolRoute(
            is_tool_request=True,
            domain="organizer",
            normalized_request=normalized,
            confidence=plan.confidence if plan.confidence != "low" else "high",
            reason=plan.reason,
            steps=plan.steps,
        )

    return plan


def _clean_text(value: object) -> str | None:
    cleaned = str(value or "").strip()
    return cleaned or None


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
