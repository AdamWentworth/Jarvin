from __future__ import annotations

import re
from dataclasses import dataclass


_ACTION_RE = re.compile(
    r"\b(?:show|list|output|check|look|find|read|create|add|schedule|book|make|put|"
    r"move|reschedule|change|update|rename|delete|remove|cancel|complete|mark|set|remind)\b",
    re.IGNORECASE,
)
_QUERY_RE = re.compile(
    r"\b(?:what(?:'s| is) on|what do i have|do i have|anything (?:on|in)|when is|which reminders?)\b",
    re.IGNORECASE,
)
_CORRECTION_RE = re.compile(
    r"\b(?:i (?:said|meant|asked)|already have|that one|the one and only|instead|not .*?(?:reminder|event))\b",
    re.IGNORECASE,
)
_CLEAR_ACTION_RE = re.compile(r"\bclear\s+(?:all|my|the|calendar|reminders?|events?)\b", re.IGNORECASE)
_META_DOMAIN_RE = re.compile(
    r"\b(?:is|was) that (?:a |an )?(?:reminder|event)|\breminder or (?:an )?event\b",
    re.IGNORECASE,
)
_CALENDAR_RE = re.compile(
    r"\b(?:calendar|agenda|events?|appointments?|meetings?)\b",
    re.IGNORECASE,
)
_REMINDER_RE = re.compile(
    r"\b(?:remind me|reminders?|routines?|to-?dos?)\b",
    re.IGNORECASE,
)
_WEATHER_RE = re.compile(
    r"\b(?:weather|forecast|temperature|degrees|rain|raining|sunny|overcast|snow|wind)\b",
    re.IGNORECASE,
)
_WEATHER_QUERY_RE = re.compile(
    r"\b(?:outside|today|tomorrow|tonight|current(?:ly)?|right now|forecast|will it|going to|is it)\b|"
    r"\bwhat(?:'s| is) the weather\b",
    re.IGNORECASE,
)

_MANAGED_DOMAINS = {"calendar", "reminder", "organizer", "weather"}


@dataclass(frozen=True)
class CapabilityGuardDecision:
    domain: str
    operation: str
    reply: str
    examples: tuple[str, ...]

    def payload(self) -> dict[str, object]:
        return {
            "status": "not_executed",
            "domain": self.domain,
            "operation": self.operation,
            "explanation": (
                "No deterministic tool accepted this request, so Jarvin blocked free-form model fallback."
            ),
            "examples": list(self.examples),
        }


def maybe_guard_unhandled_managed_request(
    text: str,
    *,
    active_domain: str | None = None,
) -> CapabilityGuardDecision | None:
    """Stop managed-domain requests from falling through to an unverifiable LLM reply.

    This runs only after every deterministic planner and tool handler declined the
    request. It is intentionally conservative: ordinary conversation still reaches
    the LLM, while calendar, reminder, organizer, and live-weather requests fail
    closed with an explicit statement that nothing was executed.
    """

    message = str(text or "").strip()
    if not message:
        return None

    domains = _matched_domains(message)
    normalized_active_domain = str(active_domain or "").strip().lower()
    if not domains and normalized_active_domain in _MANAGED_DOMAINS and _looks_contextual(message):
        domains.add(normalized_active_domain)
    if not domains:
        return None

    if domains == {"weather"}:
        if not _WEATHER_QUERY_RE.search(message):
            return None
    elif not (
        _ACTION_RE.search(message)
        or _CLEAR_ACTION_RE.search(message)
        or _QUERY_RE.search(message)
        or _CORRECTION_RE.search(message)
        or _META_DOMAIN_RE.search(message)
    ):
        return None

    domain = _resolve_domain(domains)
    operation = _infer_operation(message)
    examples = _examples_for_domain(domain)
    resource_label = {
        "calendar": "calendar data",
        "reminder": "reminder data",
        "organizer": "calendar or reminder data",
        "weather": "live weather data",
    }[domain]
    article = "an" if domain == "organizer" else "a"
    reply = (
        f"I recognized this as {article} {domain} request, but I couldn't translate it into a verified operation. "
        f"I did not read or change {resource_label}. Please rephrase it as one explicit action."
    )
    return CapabilityGuardDecision(
        domain=domain,
        operation=operation,
        reply=reply,
        examples=examples,
    )


def _matched_domains(message: str) -> set[str]:
    domains: set[str] = set()
    if _CALENDAR_RE.search(message):
        domains.add("calendar")
    if _REMINDER_RE.search(message):
        domains.add("reminder")
    if _WEATHER_RE.search(message):
        domains.add("weather")
    if "calendar" in domains and "reminder" in domains:
        return {"organizer"}
    return domains


def _looks_contextual(message: str) -> bool:
    return bool(
        _ACTION_RE.search(message)
        or _CLEAR_ACTION_RE.search(message)
        or _QUERY_RE.search(message)
        or _CORRECTION_RE.search(message)
        or _META_DOMAIN_RE.search(message)
    )


def _resolve_domain(domains: set[str]) -> str:
    if "organizer" in domains or {"calendar", "reminder"}.issubset(domains):
        return "organizer"
    return sorted(domains)[0]


def _infer_operation(message: str) -> str:
    lower = message.lower()
    if any(token in lower for token in ("delete", "remove", "cancel", "clear")):
        return "delete"
    if any(token in lower for token in ("move", "reschedule", "change", "update", "rename", "set")):
        return "update"
    if any(token in lower for token in ("create", "add", "schedule", "book", "make", "put", "remind me")):
        return "create"
    if any(token in lower for token in ("show", "list", "output", "check", "look", "find", "read", "what", "when", "will")):
        return "read"
    return "unknown"


def _examples_for_domain(domain: str) -> tuple[str, ...]:
    if domain == "calendar":
        return (
            "Show my calendar for the next 7 days.",
            "Create a calendar event called Costco tomorrow at noon.",
        )
    if domain == "reminder":
        return (
            "Show my pending reminders.",
            "Remind me tomorrow at 9 AM to go to Costco.",
        )
    if domain == "organizer":
        return (
            "Show all calendar events and reminders.",
            "Delete all calendar events and reminders, then ask me to confirm.",
        )
    return (
        "What's the weather in Burnaby today?",
        "Will it rain in Burnaby tomorrow?",
    )
