from __future__ import annotations

from dataclasses import dataclass


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
