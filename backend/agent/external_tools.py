from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

import config as cfg

DUCKDUCKGO_LITE_URL = "https://lite.duckduckgo.com/lite/"
GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"
OPEN_METEO_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

_RESULT_LINK_RE = re.compile(r'<a[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>', re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")

WEATHER_CODE_LABELS = {
    0: "Clear sky",
    1: "Mostly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Light rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Light snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Rain showers",
    81: "Moderate showers",
    82: "Violent showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Severe thunderstorm with hail",
}


@dataclass(frozen=True)
class WebSearchItem:
    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class WebSearchResult:
    provider: str
    query: str
    items: list[WebSearchItem]


@dataclass(frozen=True)
class WeatherResult:
    location_label: str
    forecast_summary: str
    temperature: str
    feels_like: str
    wind: str
    daily_outlook: str


@dataclass(frozen=True)
class CalendarEventSummary:
    starts_at: str
    title: str
    location: str


@dataclass(frozen=True)
class CalendarAgendaResult:
    calendar_id: str
    window_days: int
    events: list[CalendarEventSummary]


def google_calendar_credentials_configured() -> bool:
    return Path(cfg.settings.google_calendar_credentials_file).resolve().is_file()


def google_calendar_token_available() -> bool:
    return Path(cfg.settings.google_calendar_token_file).resolve().is_file()


def google_search_is_configured() -> bool:
    return bool(str(cfg.settings.google_search_api_key or "").strip() and str(cfg.settings.google_search_engine_id or "").strip())


def search_web(query: str, *, max_results: int = 5) -> WebSearchResult:
    q = str(query or "").strip()
    if not q:
        raise ValueError("Search query cannot be empty.")

    provider = str(cfg.settings.agent_web_search_provider or "duckduckgo_lite").strip().lower()
    if provider == "google_cse":
        return _google_cse_search(q, max_results=max_results)
    return _duckduckgo_lite_search(q, max_results=max_results)


def get_weather(location: str) -> WeatherResult:
    place = str(location or "").strip()
    if not place:
        raise ValueError("Weather location cannot be empty.")

    geo = requests.get(
        OPEN_METEO_GEOCODE_URL,
        params={"name": place, "count": 1, "language": "en", "format": "json"},
        timeout=cfg.settings.agent_command_timeout_sec,
    )
    geo.raise_for_status()
    geo_payload = geo.json()
    results = geo_payload.get("results") or []
    if not results:
        raise ValueError(f"Could not find a location for '{place}'.")

    first = results[0]
    latitude = first["latitude"]
    longitude = first["longitude"]
    location_label = ", ".join(
        part
        for part in [
            first.get("name"),
            first.get("admin1"),
            first.get("country"),
        ]
        if part
    )

    forecast = requests.get(
        OPEN_METEO_FORECAST_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "temperature_unit": cfg.settings.weather_temperature_unit,
            "wind_speed_unit": cfg.settings.weather_wind_speed_unit,
            "timezone": "auto",
            "forecast_days": 1,
        },
        timeout=cfg.settings.agent_command_timeout_sec,
    )
    forecast.raise_for_status()
    payload = forecast.json()
    current = payload.get("current", {})
    daily = payload.get("daily", {})
    current_code = int(current.get("weather_code", -1))
    summary = WEATHER_CODE_LABELS.get(current_code, f"Weather code {current_code}")
    high = _safe_daily_value(daily, "temperature_2m_max")
    low = _safe_daily_value(daily, "temperature_2m_min")
    precip = _safe_daily_value(daily, "precipitation_probability_max")

    return WeatherResult(
        location_label=location_label,
        forecast_summary=summary,
        temperature=f"{current.get('temperature_2m')}°",
        feels_like=f"{current.get('apparent_temperature')}°",
        wind=f"{current.get('wind_speed_10m')} {cfg.settings.weather_wind_speed_unit}",
        daily_outlook=f"High {high}°, low {low}°, precip {precip}%",
    )


def begin_google_calendar_auth() -> str:
    creds = _load_google_credentials()
    token_path = Path(cfg.settings.google_calendar_token_file).resolve()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return f"Google Calendar authorization complete on the host machine. Token saved to `{token_path}`."


def get_calendar_agenda(*, window_days: int = 7) -> CalendarAgendaResult:
    service = _get_calendar_service()
    now = datetime.now(timezone.utc)
    upper = now + timedelta(days=max(1, int(window_days)))
    events_result = (
        service.events()
        .list(
            calendarId=cfg.settings.google_calendar_id,
            timeMin=now.isoformat(),
            timeMax=upper.isoformat(),
            maxResults=max(1, int(cfg.settings.google_calendar_max_events)),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    items = events_result.get("items", [])
    events = [
        CalendarEventSummary(
            starts_at=_format_google_event_start(item.get("start", {})),
            title=item.get("summary") or "(untitled event)",
            location=item.get("location") or "",
        )
        for item in items
    ]
    return CalendarAgendaResult(
        calendar_id=cfg.settings.google_calendar_id,
        window_days=max(1, int(window_days)),
        events=events,
    )


def _duckduckgo_lite_search(query: str, *, max_results: int) -> WebSearchResult:
    response = requests.post(
        DUCKDUCKGO_LITE_URL,
        data={"q": query},
        timeout=cfg.settings.agent_command_timeout_sec,
        headers={"User-Agent": "Jarvin/1.0"},
    )
    response.raise_for_status()
    items: list[WebSearchItem] = []
    for match in _RESULT_LINK_RE.finditer(response.text):
        href = match.group("href")
        if not href.startswith("http"):
            continue
        title = _clean_html(match.group("title"))
        items.append(WebSearchItem(title=title or href, url=href, snippet=""))
        if len(items) >= max_results:
            break
    if not items:
        raise ValueError("No web results were returned by the configured search provider.")
    return WebSearchResult(provider="duckduckgo_lite", query=query, items=items)


def _google_cse_search(query: str, *, max_results: int) -> WebSearchResult:
    api_key = str(cfg.settings.google_search_api_key or "").strip()
    search_engine_id = str(cfg.settings.google_search_engine_id or "").strip()
    if not api_key or not search_engine_id:
        raise ValueError(
            "Google web search is configured, but the host is missing JARVIN_GOOGLE_SEARCH_API_KEY "
            "or JARVIN_GOOGLE_SEARCH_ENGINE_ID."
        )

    response = requests.get(
        GOOGLE_CSE_URL,
        params={"key": api_key, "cx": search_engine_id, "q": query, "num": max(1, min(max_results, 10))},
        timeout=cfg.settings.agent_command_timeout_sec,
    )
    response.raise_for_status()
    payload = response.json()
    items = [
        WebSearchItem(
            title=item.get("title") or item.get("link") or "(untitled result)",
            url=item.get("link") or "",
            snippet=item.get("snippet") or "",
        )
        for item in payload.get("items", [])
        if item.get("link")
    ]
    if not items:
        raise ValueError("Google search did not return any results.")
    return WebSearchResult(provider="google_cse", query=query, items=items)


def _clean_html(text: str) -> str:
    stripped = _HTML_TAG_RE.sub("", text)
    return stripped.replace("&amp;", "&").replace("&quot;", '"').strip()


def _safe_daily_value(daily: dict[str, Any], key: str) -> Any:
    values = daily.get(key) or []
    return values[0] if values else "?"


def _load_google_credentials():
    creds_path = Path(cfg.settings.google_calendar_credentials_file).resolve()
    if not creds_path.is_file():
        raise ValueError(
            "Google Calendar credentials are not configured yet. "
            f"Put your OAuth desktop client JSON at `{creds_path}` first."
        )

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise RuntimeError(
            "Google Calendar dependencies are missing. Install the updated Jarvin requirements first."
        ) from exc

    token_path = Path(cfg.settings.google_calendar_token_file).resolve()
    creds = None
    if token_path.is_file():
        creds = Credentials.from_authorized_user_file(str(token_path), GOOGLE_CALENDAR_SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), GOOGLE_CALENDAR_SCOPES)
    return flow.run_local_server(port=0)


def _get_calendar_service():
    creds = _load_google_credentials()
    token_path = Path(cfg.settings.google_calendar_token_file).resolve()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Google Calendar dependencies are missing. Install the updated Jarvin requirements first."
        ) from exc
    return build("calendar", "v3", credentials=creds)


def _format_google_event_start(start: dict[str, Any]) -> str:
    value = start.get("dateTime") or start.get("date") or ""
    if not value:
        return "Unknown time"
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return value
    if parsed.tzinfo is None:
        return parsed.strftime("%Y-%m-%d")
    return parsed.astimezone().strftime("%Y-%m-%d %I:%M %p")
