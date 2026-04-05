from __future__ import annotations

import backend.agent.weather.weather_request_tools as weather_tools
from backend.agent.integration_facade import WeatherResult


def test_weather_agent_returns_structured_payload(monkeypatch):
    monkeypatch.setattr(
        weather_tools,
        "generate_reply",
        lambda prompt, cfg=None, context=None: (
            '{"is_weather_request": true, "location_query": "Burnaby near Metrotown", '
            '"day_offset": 1, "needs_location": false, "request_summary": "tomorrow weather", '
            '"focus": ["rain", "temperature"]}'
        ),
        raising=True,
    )

    monkeypatch.setattr(
        weather_tools,
        "get_weather",
        lambda location_query, day_offset=0: WeatherResult(
            location_label="Burnaby, British Columbia, Canada",
            forecast_summary="Light rain",
            temperature="15Â°",
            feels_like="12Â°",
            wind="9 mph",
            daily_outlook="High 15Â°, low 10Â°, rain chance 70%.",
            target_label="Tomorrow",
            date_label="Sun, Apr 05",
            temperature_value=15,
            feels_like_value=None,
            high_value=15,
            low_value=10,
            precipitation_probability=70,
            weather_code=61,
            icon_name="rain",
            is_current_day=False,
        ),
        raising=True,
    )

    result = weather_tools.maybe_handle_weather_request(
        "Will I need an umbrella near Metrotown tomorrow?",
        conversation_id=101,
    )

    assert result is not None
    assert "Tomorrow in Burnaby" in result.reply
    assert result.payload["location_label"] == "Burnaby, British Columbia, Canada"
    assert result.payload["icon_name"] == "rain"
    assert result.payload["precipitation_probability"] == 70


def test_weather_agent_asks_for_location_when_missing(monkeypatch):
    monkeypatch.setattr(
        weather_tools,
        "generate_reply",
        lambda prompt, cfg=None, context=None: (
            '{"is_weather_request": true, "location_query": null, '
            '"day_offset": 0, "needs_location": true, "request_summary": "weather", "focus": []}'
        ),
        raising=True,
    )

    result = weather_tools.maybe_handle_weather_request("How is it outside?", conversation_id=102)

    assert result is not None
    assert result.payload == {}
    assert "need the place" in result.reply


def test_weather_agent_uses_recent_context_for_follow_up(monkeypatch):
    weather_tools.set_weather_context(
        103,
        weather_tools.WeatherConversationContext(
            location_query="Burnaby, BC",
            location_label="Burnaby, British Columbia, Canada",
            day_offset=0,
            awaiting_location=False,
        ),
    )

    monkeypatch.setattr(
        weather_tools,
        "generate_reply",
        lambda prompt, cfg=None, context=None: (
            '{"is_weather_request": true, "location_query": null, '
            '"day_offset": 1, "needs_location": false, "request_summary": "tomorrow", "focus": ["rain"]}'
        ),
        raising=True,
    )

    captured = {}

    def fake_get_weather(location_query, day_offset=0):
        captured["location_query"] = location_query
        captured["day_offset"] = day_offset
        return WeatherResult(
            location_label="Burnaby, British Columbia, Canada",
            forecast_summary="Overcast",
            temperature="13Â°",
            feels_like="Low 9Â°",
            wind="7 mph",
            daily_outlook="High 13Â°, low 9Â°, rain chance 20%.",
            target_label="Tomorrow",
            date_label="Sun, Apr 05",
            temperature_value=13,
            feels_like_value=None,
            high_value=13,
            low_value=9,
            precipitation_probability=20,
            weather_code=3,
            icon_name="cloud",
            is_current_day=False,
        )

    monkeypatch.setattr(weather_tools, "get_weather", fake_get_weather, raising=True)

    result = weather_tools.maybe_handle_weather_request("How about tomorrow?", conversation_id=103)

    assert result is not None
    assert captured == {"location_query": "Burnaby, BC", "day_offset": 1}
    assert result.payload["target_label"] == "Tomorrow"


def test_weather_agent_ignores_meta_weather_complaint_without_context(monkeypatch):
    monkeypatch.setattr(
        weather_tools,
        "generate_reply",
        lambda prompt, cfg=None, context=None: (
            '{"is_weather_request": false, "location_query": null, '
            '"day_offset": 0, "needs_location": false, "request_summary": "", "focus": []}'
        ),
        raising=True,
    )

    result = weather_tools.maybe_handle_weather_request("Why do you not just use the weather API?")

    assert result is None

