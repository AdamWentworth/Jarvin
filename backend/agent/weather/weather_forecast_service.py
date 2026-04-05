from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import requests

import config as cfg
from backend.agent.integration_models import WeatherResult

OPEN_METEO_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

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

