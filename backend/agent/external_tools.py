from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

import config as cfg

DUCKDUCKGO_LITE_URL = "https://lite.duckduckgo.com/lite/"
GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"
OPEN_METEO_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
SEARCH_USER_AGENT = "Jarvin/1.0 (+https://jarvin.local)"
MAX_WEB_PAGE_CHARS = 7000
MAX_WEB_PAGES_PER_QUERY = 3

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
class WebPageExtract:
    url: str
    title: str
    excerpt: str


@dataclass(frozen=True)
class WebResearchResult:
    provider: str
    query: str
    items: list[WebSearchItem]
    pages: list[WebPageExtract]


@dataclass(frozen=True)
class WeatherResult:
    location_label: str
    forecast_summary: str
    temperature: str
    feels_like: str
    wind: str
    daily_outlook: str
    target_label: str = "Today"
    date_label: str = ""
    temperature_value: float | None = None
    feels_like_value: float | None = None
    high_value: float | None = None
    low_value: float | None = None
    precipitation_probability: int | None = None
    weather_code: int | None = None
    icon_name: str = "cloud"
    is_current_day: bool = True


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


@dataclass(frozen=True)
class CalendarEventMatch:
    event_id: str
    title: str
    starts_at: str
    ends_at: str
    location: str
    description: str = ""


@dataclass(frozen=True)
class CalendarEventDetails:
    event_id: str
    calendar_id: str
    starts_at: str
    ends_at: str
    title: str
    location: str
    description: str


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


def browse_search_results(
    query: str,
    *,
    max_results: int = 5,
    max_pages: int = MAX_WEB_PAGES_PER_QUERY,
) -> WebResearchResult:
    results = search_web(query, max_results=max(max_results, max_pages))
    pages: list[WebPageExtract] = []
    for item in results.items:
        if len(pages) >= max(1, int(max_pages)):
            break
        try:
            page = fetch_web_page(item.url, fallback_title=item.title)
        except Exception:
            continue
        if page.excerpt:
            pages.append(page)
    return WebResearchResult(
        provider=results.provider,
        query=results.query,
        items=results.items,
        pages=pages,
    )


def fetch_web_page(url: str, *, fallback_title: str = "") -> WebPageExtract:
    target = str(url or "").strip()
    if not target:
        raise ValueError("Web page URL cannot be empty.")

    response = requests.get(
        target,
        timeout=cfg.settings.agent_command_timeout_sec,
        headers={"User-Agent": SEARCH_USER_AGENT},
    )
    response.raise_for_status()
    content_type = str(response.headers.get("content-type") or "").lower()
    text = response.text or ""
    if "html" in content_type or "<html" in text.lower():
        parsed_title, excerpt = _extract_html_page(text)
    else:
        parsed_title = fallback_title or target
        excerpt = _normalize_text_block(text)

    excerpt = excerpt[:MAX_WEB_PAGE_CHARS].strip()
    if not excerpt:
        raise ValueError(f"No readable text was extracted from {target}.")

    return WebPageExtract(
        url=target,
        title=parsed_title or fallback_title or _display_url(target),
        excerpt=excerpt,
    )


def get_weather(location: str, *, day_offset: int = 0) -> WeatherResult:
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
            "forecast_days": max(1, min(int(day_offset) + 1, 7)),
        },
        timeout=cfg.settings.agent_command_timeout_sec,
    )
    forecast.raise_for_status()
    payload = forecast.json()
    current = payload.get("current", {})
    daily = payload.get("daily", {})
    offset = max(0, int(day_offset))
    daily_codes = daily.get("weather_code") or []
    daily_highs = daily.get("temperature_2m_max") or []
    daily_lows = daily.get("temperature_2m_min") or []
    daily_precip = daily.get("precipitation_probability_max") or []
    daily_times = daily.get("time") or []
    if offset >= len(daily_highs):
        raise ValueError(f"This host could not load the weather forecast that far ahead for '{place}'.")
    day_code = int(daily_codes[offset]) if offset < len(daily_codes) and daily_codes[offset] is not None else -1
    summary = WEATHER_CODE_LABELS.get(day_code, f"Weather code {day_code}")
    high = daily_highs[offset] if offset < len(daily_highs) else "?"
    low = daily_lows[offset] if offset < len(daily_lows) else "?"
    precip = daily_precip[offset] if offset < len(daily_precip) else "?"
    date_label = str(daily_times[offset]) if offset < len(daily_times) else ""
    current_temp = current.get("temperature_2m")
    current_feels_like = current.get("apparent_temperature")
    current_wind = current.get("wind_speed_10m")
    current_code = int(current.get("weather_code", day_code if day_code >= 0 else -1))
    is_current_day = offset == 0

    return WeatherResult(
        location_label=location_label,
        forecast_summary=summary,
        temperature=f"{current_temp}°" if is_current_day and current_temp is not None else f"{high}°",
        feels_like=f"{current_feels_like}°" if is_current_day and current_feels_like is not None else f"Low {low}°",
        wind=f"{current_wind} {cfg.settings.weather_wind_speed_unit}",
        daily_outlook=f"High {high}°, low {low}°, precip {precip}%",
        target_label=_weather_target_label(offset),
        date_label=date_label,
        temperature_value=_float_or_none(current_temp if is_current_day else high),
        feels_like_value=_float_or_none(current_feels_like if is_current_day else None),
        high_value=_float_or_none(high),
        low_value=_float_or_none(low),
        precipitation_probability=_int_or_none(precip),
        weather_code=current_code if is_current_day else day_code,
        icon_name=_weather_icon_name(current_code if is_current_day else day_code),
        is_current_day=is_current_day,
    )


def begin_google_calendar_auth() -> str:
    creds = _load_google_credentials(interactive=True)
    token_path = Path(cfg.settings.google_calendar_token_file).resolve()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return f"Google Calendar authorization complete on the host machine. Token saved to `{token_path}`."


def get_calendar_agenda(*, window_days: int = 7) -> CalendarAgendaResult:
    service = _get_calendar_service(interactive=False)
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


def create_calendar_event_from_text(text: str) -> CalendarEventSummary:
    details = str(text or "").strip()
    if not details:
        raise ValueError("I need event details before I can create a calendar event.")

    service = _get_calendar_service(interactive=False)
    event = (
        service.events()
        .quickAdd(
            calendarId=cfg.settings.google_calendar_id,
            text=details,
            sendUpdates="none",
        )
        .execute()
    )
    return _event_to_summary(event)


def find_calendar_events(query: str, *, window_days: int = 30, max_results: int = 5) -> list[CalendarEventMatch]:
    text = str(query or "").strip()
    if not text:
        raise ValueError("I need an event name or description to search your calendar.")

    service = _get_calendar_service(interactive=False)
    now = datetime.now(timezone.utc)
    upper = now + timedelta(days=max(1, int(window_days)))
    response = (
        service.events()
        .list(
            calendarId=cfg.settings.google_calendar_id,
            timeMin=now.isoformat(),
            timeMax=upper.isoformat(),
            q=text,
            maxResults=max(1, int(max_results)),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return [_event_to_match(item) for item in response.get("items", [])]


def get_calendar_event_details(event_id: str) -> CalendarEventDetails:
    target_id = str(event_id or "").strip()
    if not target_id:
        raise ValueError("Missing calendar event id.")

    service = _get_calendar_service(interactive=False)
    event = service.events().get(calendarId=cfg.settings.google_calendar_id, eventId=target_id).execute()
    return _event_to_details(event)


def delete_calendar_event(event_id: str) -> CalendarEventSummary:
    target_id = str(event_id or "").strip()
    if not target_id:
        raise ValueError("Missing calendar event id.")

    service = _get_calendar_service(interactive=False)
    event = service.events().get(calendarId=cfg.settings.google_calendar_id, eventId=target_id).execute()
    summary = _event_to_summary(event)
    service.events().delete(calendarId=cfg.settings.google_calendar_id, eventId=target_id, sendUpdates="none").execute()
    return summary


def update_calendar_event_fields(
    event_id: str,
    *,
    title: str | None = None,
    location: str | None = None,
    description: str | None = None,
    new_start_iso: str | None = None,
    new_end_iso: str | None = None,
) -> CalendarEventDetails:
    target_id = str(event_id or "").strip()
    if not target_id:
        raise ValueError("Missing calendar event id.")

    body: dict[str, Any] = {}
    if title is not None:
        body["summary"] = title
    if location is not None:
        body["location"] = location
    if description is not None:
        body["description"] = description

    service = _get_calendar_service(interactive=False)
    if new_start_iso is not None or new_end_iso is not None:
        if not new_start_iso or not new_end_iso:
            raise ValueError("Both the new start and end time are required when rescheduling an event.")
        existing = service.events().get(calendarId=cfg.settings.google_calendar_id, eventId=target_id).execute()
        timezone_name = (
            existing.get("start", {}).get("timeZone")
            or existing.get("end", {}).get("timeZone")
            or "UTC"
        )
        body["start"] = {"dateTime": new_start_iso, "timeZone": timezone_name}
        body["end"] = {"dateTime": new_end_iso, "timeZone": timezone_name}

    if not body:
        raise ValueError("I need at least one calendar field to update.")

    patched = (
        service.events()
        .patch(
            calendarId=cfg.settings.google_calendar_id,
            eventId=target_id,
            body=body,
            sendUpdates="none",
        )
        .execute()
    )
    return _event_to_details(patched)


def reschedule_calendar_event(event_id: str, *, new_start_iso: str, new_end_iso: str) -> CalendarEventSummary:
    target_id = str(event_id or "").strip()
    if not target_id:
        raise ValueError("Missing calendar event id.")

    patched = update_calendar_event_fields(
        target_id,
        new_start_iso=new_start_iso,
        new_end_iso=new_end_iso,
    )
    return CalendarEventSummary(
        starts_at=patched.starts_at,
        title=patched.title,
        location=patched.location,
    )


def prepare_reschedule_times(event: CalendarEventMatch, when_text: str) -> tuple[str, str]:
    start_dt = _parse_event_datetime(event.starts_at)
    end_dt = _parse_event_datetime(event.ends_at)
    duration = end_dt - start_dt if end_dt > start_dt else timedelta(hours=1)
    new_start = _parse_when_text(when_text, base_start=start_dt)
    new_end = new_start + duration
    return new_start.isoformat(), new_end.isoformat()


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


class _ReadableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._capture_title = False
        self._title_chunks: list[str] = []
        self._text_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "svg", "noscript"}:
            self._skip_depth += 1
            return
        if lowered == "title":
            self._capture_title = True
        if lowered in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "blockquote", "pre", "br"}:
            self._text_chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "svg", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if lowered == "title":
            self._capture_title = False
        if lowered in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "blockquote", "pre"}:
            self._text_chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        cleaned = str(data or "").strip()
        if not cleaned:
            return
        if self._capture_title:
            self._title_chunks.append(cleaned)
        self._text_chunks.append(cleaned)

    @property
    def title(self) -> str:
        return _normalize_text_block(" ".join(self._title_chunks))

    @property
    def text(self) -> str:
        return _normalize_text_block("\n".join(self._text_chunks))


def _clean_html(text: str) -> str:
    stripped = _HTML_TAG_RE.sub("", text)
    return stripped.replace("&amp;", "&").replace("&quot;", '"').strip()


def _extract_html_page(html: str) -> tuple[str, str]:
    parser = _ReadableHTMLParser()
    parser.feed(html)
    parser.close()
    return parser.title, _select_relevant_excerpt(parser.text)


def _select_relevant_excerpt(text: str, *, max_blocks: int = 8) -> str:
    lines = [line.strip() for line in text.splitlines()]
    kept: list[str] = []
    seen: set[str] = set()
    for line in lines:
        normalized = _normalize_text_block(line)
        if len(normalized) < 35:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        if any(
            noise in lowered
            for noise in (
                "cookie",
                "privacy policy",
                "terms of service",
                "sign in",
                "log in",
                "all rights reserved",
                "advertisement",
                "subscribe",
            )
        ):
            continue
        kept.append(normalized)
        seen.add(lowered)
        if len(kept) >= max_blocks:
            break
    return "\n".join(kept)


def _normalize_text_block(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _display_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc or url
    path = parsed.path.rstrip("/")
    return f"{host}{path}"


def _safe_daily_value(daily: dict[str, Any], key: str) -> Any:
    values = daily.get(key) or []
    return values[0] if values else "?"


def _weather_target_label(day_offset: int) -> str:
    if day_offset <= 0:
        return "Today"
    if day_offset == 1:
        return "Tomorrow"
    target = datetime.now().date() + timedelta(days=day_offset)
    return target.strftime("%A")


def _weather_icon_name(weather_code: int) -> str:
    if weather_code == 0:
        return "sun"
    if weather_code in {1, 2}:
        return "cloud-sun"
    if weather_code == 3:
        return "cloud"
    if weather_code in {45, 48}:
        return "fog"
    if weather_code in {51, 53, 55, 61, 63, 65, 80, 81, 82}:
        return "rain"
    if weather_code in {71, 73, 75}:
        return "snow"
    if weather_code in {95, 96, 99}:
        return "storm"
    return "cloud"


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _format_temperature(value: Any) -> str:
    number = _float_or_none(value)
    if number is None:
        return "?"
    return f"{int(round(number))}\N{DEGREE SIGN}"


def _format_weather_date_label(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    return parsed.strftime("%a, %b %d")


def get_weather(location: str, *, day_offset: int = 0) -> WeatherResult:
    """
    Override the earlier bootstrap implementation with a richer, day-aware payload
    for both natural-language weather reasoning and the UI weather card.
    """
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
        for part in [first.get("name"), first.get("admin1"), first.get("country")]
        if part
    )

    offset = max(0, int(day_offset))
    forecast = requests.get(
        OPEN_METEO_FORECAST_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max",
            "temperature_unit": cfg.settings.weather_temperature_unit,
            "wind_speed_unit": cfg.settings.weather_wind_speed_unit,
            "timezone": "auto",
            "forecast_days": max(1, min(offset + 1, 7)),
        },
        timeout=cfg.settings.agent_command_timeout_sec,
    )
    forecast.raise_for_status()
    payload = forecast.json()
    current = payload.get("current", {})
    daily = payload.get("daily", {})
    daily_codes = daily.get("weather_code") or []
    daily_highs = daily.get("temperature_2m_max") or []
    daily_lows = daily.get("temperature_2m_min") or []
    daily_precip = daily.get("precipitation_probability_max") or []
    daily_wind = daily.get("wind_speed_10m_max") or []
    daily_times = daily.get("time") or []

    if offset >= len(daily_highs):
        raise ValueError(f"This host could not load the weather forecast that far ahead for '{place}'.")

    day_code = int(daily_codes[offset]) if offset < len(daily_codes) and daily_codes[offset] is not None else -1
    summary = WEATHER_CODE_LABELS.get(day_code, f"Weather code {day_code}")
    high = daily_highs[offset] if offset < len(daily_highs) else None
    low = daily_lows[offset] if offset < len(daily_lows) else None
    precip = daily_precip[offset] if offset < len(daily_precip) else None
    daily_wind_speed = daily_wind[offset] if offset < len(daily_wind) else None
    date_label = str(daily_times[offset]) if offset < len(daily_times) else ""

    current_temp = current.get("temperature_2m")
    current_feels_like = current.get("apparent_temperature")
    current_wind = current.get("wind_speed_10m")
    current_code = int(current.get("weather_code", day_code if day_code >= 0 else -1))
    is_current_day = offset == 0
    target_code = current_code if is_current_day else day_code
    temperature_value = current_temp if is_current_day else high
    feels_like_value = current_feels_like if is_current_day else None
    wind_value = current_wind if is_current_day else daily_wind_speed
    precip_value = _int_or_none(precip)
    wind_float = _float_or_none(wind_value)

    return WeatherResult(
        location_label=location_label,
        forecast_summary=summary,
        temperature=_format_temperature(temperature_value),
        feels_like=(
            _format_temperature(feels_like_value)
            if is_current_day and feels_like_value is not None
            else f"Low {_format_temperature(low)}"
        ),
        wind=(
            f"{wind_float:g} {cfg.settings.weather_wind_speed_unit}"
            if wind_float is not None
            else f"? {cfg.settings.weather_wind_speed_unit}"
        ),
        daily_outlook=(
            f"High {_format_temperature(high)}, low {_format_temperature(low)}, "
            f"rain chance {precip_value if precip_value is not None else '?'}%."
        ),
        target_label=_weather_target_label(offset),
        date_label=_format_weather_date_label(date_label),
        temperature_value=_float_or_none(temperature_value),
        feels_like_value=_float_or_none(feels_like_value),
        high_value=_float_or_none(high),
        low_value=_float_or_none(low),
        precipitation_probability=precip_value,
        weather_code=target_code,
        icon_name=_weather_icon_name(target_code),
        is_current_day=is_current_day,
    )


def _load_google_credentials(*, interactive: bool):
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

    if creds and not creds.has_scopes(GOOGLE_CALENDAR_SCOPES):
        if not interactive:
            raise ValueError(
                "Google Calendar needs to be re-authorized on this host because Jarvin now requests broader calendar permissions. "
                "Ask me to connect your Google Calendar again."
            )
        creds = None

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    if not interactive:
        raise ValueError(
            "Google Calendar is not authorized on this host yet. Ask me to connect your Google Calendar and I will start the OAuth flow."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), GOOGLE_CALENDAR_SCOPES)
    return flow.run_local_server(port=0)


def _get_calendar_service(*, interactive: bool):
    creds = _load_google_credentials(interactive=interactive)
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


def _event_to_summary(event: dict[str, Any]) -> CalendarEventSummary:
    return CalendarEventSummary(
        starts_at=_format_google_event_start(event.get("start", {})),
        title=event.get("summary") or "(untitled event)",
        location=event.get("location") or "",
    )


def _event_to_match(event: dict[str, Any]) -> CalendarEventMatch:
    return CalendarEventMatch(
        event_id=event.get("id") or "",
        title=event.get("summary") or "(untitled event)",
        starts_at=event.get("start", {}).get("dateTime") or event.get("start", {}).get("date") or "",
        ends_at=event.get("end", {}).get("dateTime") or event.get("end", {}).get("date") or "",
        location=event.get("location") or "",
        description=event.get("description") or "",
    )


def _event_to_details(event: dict[str, Any]) -> CalendarEventDetails:
    return CalendarEventDetails(
        event_id=event.get("id") or "",
        calendar_id=event.get("organizer", {}).get("email") or cfg.settings.google_calendar_id,
        starts_at=_format_google_event_start(event.get("start", {})),
        ends_at=_format_google_event_start(event.get("end", {})),
        title=event.get("summary") or "(untitled event)",
        location=event.get("location") or "",
        description=event.get("description") or "",
    )


def _parse_event_datetime(value: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        return datetime.now().astimezone()
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"Could not parse calendar event time '{value}'.") from exc
    if parsed.tzinfo is None:
        local_tz = datetime.now().astimezone().tzinfo
        return datetime.combine(parsed.date(), time.min, tzinfo=local_tz)
    return parsed


def _parse_when_text(text: str, *, base_start: datetime) -> datetime:
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("I need the new date or time to reschedule that event.")

    tzinfo = base_start.tzinfo or datetime.now().astimezone().tzinfo
    lower = raw.lower()

    parsed_date = _extract_explicit_date(lower) or _extract_relative_date(lower, base_start.date())
    parsed_time = _extract_time(lower)

    if parsed_date is None and parsed_time is None:
        raise ValueError(
            "I could not understand the new date or time. Try something like 'Friday at 2pm' or 'tomorrow at noon'."
        )

    if parsed_date is None:
        parsed_date = base_start.date()
    if parsed_time is None:
        parsed_time = base_start.timetz().replace(tzinfo=None)

    return datetime.combine(parsed_date, parsed_time, tzinfo=tzinfo)


def _extract_explicit_date(text: str) -> date | None:
    iso_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if iso_match:
        year, month, day = map(int, iso_match.groups())
        return date(year, month, day)

    slash_match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", text)
    if slash_match:
        month = int(slash_match.group(1))
        day = int(slash_match.group(2))
        year = int(slash_match.group(3)) if slash_match.group(3) else datetime.now().year
        if year < 100:
            year += 2000
        return date(year, month, day)

    return None


def _extract_relative_date(text: str, base_date: date) -> date | None:
    today = datetime.now().date()
    if "today" in text:
        return today
    if "tomorrow" in text:
        return today + timedelta(days=1)
    if "next week" in text:
        return base_date + timedelta(days=7)

    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    for label, index in weekdays.items():
        if label in text:
            days_ahead = (index - base_date.weekday()) % 7
            if days_ahead == 0 or f"next {label}" in text:
                days_ahead = 7 if days_ahead == 0 else days_ahead + 7
            return base_date + timedelta(days=days_ahead)

    return None


def _extract_time(text: str) -> time | None:
    if "noon" in text:
        return time(hour=12, minute=0)
    if "midnight" in text:
        return time(hour=0, minute=0)

    match = re.search(r"\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text)
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = match.group(3)

    if meridiem:
        meridiem = meridiem.lower()
        if meridiem == "pm" and hour != 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0

    if hour > 23 or minute > 59:
        raise ValueError("I couldn't understand that time value.")

    return time(hour=hour, minute=minute)
