from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import config as cfg
from backend.agent.external_tools import WeatherResult, get_weather
from backend.ai_engine import build_jarvin_config, generate_reply

_WEATHER_KEYWORDS = (
    "weather",
    "forecast",
    "rain",
    "raining",
    "sunny",
    "overcast",
    "cloudy",
    "temperature",
    "degrees",
    "hot",
    "cold",
    "snow",
    "wind",
    "umbrella",
    "outside",
)


@dataclass(frozen=True)
class WeatherPlan:
    is_weather_request: bool
    location_query: str | None = None
    day_offset: int = 0
    needs_location: bool = False
    request_summary: str = ""
    focus: tuple[str, ...] = ()


@dataclass(frozen=True)
class WeatherToolResult:
    reply: str
    payload: dict[str, object]


@dataclass(frozen=True)
class WeatherConversationContext:
    location_query: str | None = None
    location_label: str | None = None
    day_offset: int = 0
    awaiting_location: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=15))


_weather_context: dict[str, WeatherConversationContext] = {}


def maybe_handle_weather_request(text: str, *, conversation_id: int | None = None) -> WeatherToolResult | None:
    message = (text or "").strip()
    if not message:
        return None

    context = get_weather_context(conversation_id)
    if not _looks_weather_related(message, context):
        return None

    plan = _plan_weather_request(message, context=context)
    if not plan.is_weather_request and context is None:
        return None

    location_query = _resolve_location_query(message, plan=plan, context=context)
    day_offset = _resolve_day_offset(message, plan=plan, context=context)

    if not location_query:
        set_weather_context(
            conversation_id,
            WeatherConversationContext(
                location_query=context.location_query if context else None,
                location_label=context.location_label if context else None,
                day_offset=day_offset,
                awaiting_location=True,
            ),
        )
        return WeatherToolResult(
            reply=(
                "I can check that, but I still need the place. "
                "Tell me the city or neighborhood, like `Burnaby near Metrotown`."
            ),
            payload={},
        )

    try:
        report = get_weather(location_query, day_offset=day_offset)
    except Exception as exc:
        set_weather_context(
            conversation_id,
            WeatherConversationContext(
                location_query=location_query,
                location_label=context.location_label if context else None,
                day_offset=day_offset,
                awaiting_location=True,
            ),
        )
        detail = str(exc).strip()
        return WeatherToolResult(
            reply=(
                f"I couldn't pin down the place from `{location_query}`. "
                f"Try the city or neighborhood more directly, like `Burnaby near Metrotown`. {detail}"
            ).strip(),
            payload={},
        )

    set_weather_context(
        conversation_id,
        WeatherConversationContext(
            location_query=location_query,
            location_label=report.location_label,
            day_offset=day_offset,
            awaiting_location=False,
        ),
    )
    return WeatherToolResult(
        reply=_render_weather_reply(report),
        payload=_weather_payload(report, requested_location=location_query),
    )


def get_weather_context(conversation_id: int | None) -> WeatherConversationContext | None:
    key = _context_key(conversation_id)
    context = _weather_context.get(key)
    if context is None:
        return None
    if context.expires_at <= datetime.now(timezone.utc):
        _weather_context.pop(key, None)
        return None
    return context


def set_weather_context(conversation_id: int | None, context: WeatherConversationContext) -> None:
    _weather_context[_context_key(conversation_id)] = context


def _context_key(conversation_id: int | None) -> str:
    return str(conversation_id) if conversation_id is not None else "__default__"


def _looks_weather_related(message: str, context: WeatherConversationContext | None) -> bool:
    lower = message.lower()
    if any(token in lower for token in _WEATHER_KEYWORDS):
        return True
    if context is None:
        return False
    if any(token in lower for token in ("today", "tomorrow", "tonight", "later", "rain", "sun", "degrees")):
        return True
    return context.awaiting_location or len(message.split()) <= 6


def _plan_weather_request(message: str, *, context: WeatherConversationContext | None) -> WeatherPlan:
    context_block = _weather_context_prompt(context)
    system = (
        "You extract weather tool arguments for Jarvin. "
        "Return JSON only with keys: "
        "is_weather_request (boolean), location_query (string|null), day_offset (integer), "
        "needs_location (boolean), request_summary (string), focus (array of strings). "
        "Use day_offset 0 for today/current, 1 for tomorrow, and 2+ for later days. "
        "If the user is correcting or clarifying a previous weather request, treat it as a weather request. "
        "If location is implied by recent context, location_query can be null. "
        "Do not answer the weather question itself."
    )
    prompt = f"Recent weather context:\n{context_block}\n\nUser message:\n{message}"
    cfg_obj = build_jarvin_config(
        mode="agent_strong",
        system_instructions=system,
        temperature=0.1,
        max_tokens=220,
    )
    raw = generate_reply(prompt, cfg=cfg_obj, context=None)
    data = _parse_json_object(raw)
    focus = data.get("focus") or []
    if not isinstance(focus, list):
        focus = []
    return WeatherPlan(
        is_weather_request=bool(data.get("is_weather_request")),
        location_query=_clean_text(data.get("location_query")),
        day_offset=max(0, int(data.get("day_offset") or 0)),
        needs_location=bool(data.get("needs_location")),
        request_summary=str(data.get("request_summary") or "").strip(),
        focus=tuple(str(item).strip() for item in focus if str(item).strip()),
    )


def _resolve_location_query(
    message: str,
    *,
    plan: WeatherPlan,
    context: WeatherConversationContext | None,
) -> str:
    location = _clean_text(plan.location_query)
    lower = message.lower()
    if location in {"here", "outside", "outside here", "around here"}:
        location = ""
    if location:
        return location
    if context and context.location_query and not context.awaiting_location:
        return context.location_query
    if any(token in lower for token in ("here", "outside", "outside here")) and cfg.settings.default_weather_location:
        return str(cfg.settings.default_weather_location).strip()
    if context and context.awaiting_location and len(message.split()) <= 10:
        return _clean_text(message)
    return ""


def _resolve_day_offset(
    message: str,
    *,
    plan: WeatherPlan,
    context: WeatherConversationContext | None,
) -> int:
    lower = message.lower()
    if "tomorrow" in lower:
        return 1
    if "today" in lower or "right now" in lower or "outside" in lower:
        return 0
    if plan.day_offset:
        return plan.day_offset
    if context is not None and any(token in lower for token in ("how about", "what about", "and")):
        return context.day_offset
    return 0


def _render_weather_reply(report: WeatherResult) -> str:
    if report.is_current_day:
        return (
            f"{report.target_label} in {report.location_label}: {report.forecast_summary}. "
            f"It is {report.temperature} right now"
            + (f", feels like {report.feels_like}" if report.feels_like_value is not None else "")
            + f". {report.daily_outlook}."
        )
    return (
        f"{report.target_label} in {report.location_label}: {report.forecast_summary}. "
        f"{report.daily_outlook}."
    )


def _weather_payload(report: WeatherResult, *, requested_location: str) -> dict[str, object]:
    return {
        "location_query": requested_location,
        "location_label": report.location_label,
        "target_label": report.target_label,
        "date_label": report.date_label,
        "summary": report.forecast_summary,
        "icon_name": report.icon_name,
        "temperature": report.temperature,
        "feels_like": report.feels_like,
        "temperature_value": report.temperature_value,
        "feels_like_value": report.feels_like_value,
        "high_value": report.high_value,
        "low_value": report.low_value,
        "precipitation_probability": report.precipitation_probability,
        "wind": report.wind,
        "daily_outlook": report.daily_outlook,
        "is_current_day": report.is_current_day,
        "source": "open-meteo",
    }


def _weather_context_prompt(context: WeatherConversationContext | None) -> str:
    if context is None:
        return "(none)"
    return (
        f"location_query={context.location_query or ''}\n"
        f"location_label={context.location_label or ''}\n"
        f"day_offset={context.day_offset}\n"
        f"awaiting_location={context.awaiting_location}"
    )


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


def _clean_text(value: object) -> str:
    return str(value or "").strip().rstrip("?.!,")
