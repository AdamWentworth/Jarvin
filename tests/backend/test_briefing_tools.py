from __future__ import annotations

from datetime import datetime, timedelta

import backend.agent.brief_planner as brief_planner
import backend.agent.briefing_tools as briefing_tools


def test_morning_brief_combines_weather_calendar_and_reminders(monkeypatch):
    now = datetime.now().astimezone()

    monkeypatch.setattr(
        briefing_tools,
        "get_user_profile",
        lambda: {"name": "Captain Monk", "goal": "Run the remote Jarvin experiment"},
        raising=True,
    )
    monkeypatch.setattr(
        briefing_tools.cfg.settings,
        "default_weather_location",
        "Seattle",
        raising=False,
    )
    monkeypatch.setattr(
        briefing_tools,
        "get_weather",
        lambda location: type(
            "Weather",
            (),
            {
                "location_label": "Seattle, Washington, United States",
                "forecast_summary": "Clear sky",
                "temperature": "48°",
                "feels_like": "46°",
                "daily_outlook": "High 58°, low 44°, precip 0%",
            },
        )(),
        raising=True,
    )
    monkeypatch.setattr(briefing_tools, "google_calendar_credentials_configured", lambda: True, raising=True)
    monkeypatch.setattr(briefing_tools, "google_calendar_token_available", lambda: True, raising=True)
    monkeypatch.setattr(
        briefing_tools,
        "get_calendar_agenda",
        lambda window_days=1: type(
            "Agenda",
            (),
            {
                "events": [
                    type("Event", (), {"starts_at": "2026-04-04 10:00 AM", "title": "Standup", "location": "Desk"})()
                ]
            },
        )(),
        raising=True,
    )
    monkeypatch.setattr(
        briefing_tools,
        "list_reminders",
        lambda status="pending", limit=50: [
            {
                "id": 1,
                "title": "Call mom",
                "due_at": (now + timedelta(hours=2)).isoformat(),
                "recurrence": "once",
                "is_overdue": False,
            }
        ],
        raising=True,
    )

    reply = briefing_tools.build_morning_brief()

    assert "Morning brief" in reply
    assert "Captain Monk" in reply
    assert "Seattle" in reply
    assert "Standup" in reply
    assert "Call mom" in reply


def test_brief_request_parser_handles_natural_language(monkeypatch):
    monkeypatch.setattr(
        briefing_tools,
        "build_morning_brief",
        lambda location_hint=None, day_offset=0: f"brief::{location_hint or 'default'}::{day_offset}",
        raising=True,
    )

    reply = briefing_tools.maybe_handle_brief_request("Give me my morning brief for Portland")

    assert reply == "brief::Portland::0"


def test_brief_reports_missing_calendar_and_weather_location(monkeypatch):
    monkeypatch.setattr(briefing_tools, "get_user_profile", lambda: {}, raising=True)
    monkeypatch.setattr(briefing_tools.cfg.settings, "default_weather_location", "", raising=False)
    monkeypatch.setattr(briefing_tools, "google_calendar_credentials_configured", lambda: False, raising=True)
    monkeypatch.setattr(
        briefing_tools,
        "list_reminders",
        lambda status="pending", limit=50: [],
        raising=True,
    )

    reply = briefing_tools.build_morning_brief()

    assert "Weather: no default location is configured yet." in reply
    assert "Calendar: not connected yet" in reply
    assert "nothing due for today" in reply


def test_brief_request_parser_handles_rundown_followed_by_tomorrow(monkeypatch):
    monkeypatch.setattr(
        briefing_tools,
        "build_morning_brief",
        lambda location_hint=None, day_offset=0: f"brief::{location_hint or 'default'}::{day_offset}",
        raising=True,
    )

    first = briefing_tools.maybe_handle_brief_request("Give me the rundown for today in Portland", conversation_id=61)
    second = briefing_tools.maybe_handle_brief_request("How about tomorrow?", conversation_id=61)

    assert first == "brief::Portland::0"
    assert second == "brief::Portland::1"
    brief_planner.clear_brief_context(61)


def test_morning_brief_can_target_tomorrow(monkeypatch):
    now = datetime.now().astimezone()
    tomorrow = now + timedelta(days=1)

    monkeypatch.setattr(briefing_tools, "get_user_profile", lambda: {}, raising=True)
    monkeypatch.setattr(briefing_tools.cfg.settings, "default_weather_location", "Seattle", raising=False)
    monkeypatch.setattr(
        briefing_tools,
        "get_weather",
        lambda location, day_offset=0: type(
            "Weather",
            (),
            {
                "location_label": "Seattle, Washington, United States",
                "target_label": "Tomorrow",
                "forecast_summary": "Rain showers",
                "temperature": "55°",
                "feels_like": "Low 48°",
                "daily_outlook": "High 55°, low 48°, rain chance 80%.",
                "is_current_day": False,
            },
        )(),
        raising=True,
    )
    monkeypatch.setattr(briefing_tools, "google_calendar_credentials_configured", lambda: True, raising=True)
    monkeypatch.setattr(briefing_tools, "google_calendar_token_available", lambda: True, raising=True)
    monkeypatch.setattr(
        briefing_tools,
        "get_calendar_agenda",
        lambda window_days=2: type(
            "Agenda",
            (),
            {
                "events": [
                    type("Event", (), {"starts_at": tomorrow.strftime("%Y-%m-%d %I:%M %p"), "title": "Coffee", "location": "Cafe"})()
                ]
            },
        )(),
        raising=True,
    )
    monkeypatch.setattr(
        briefing_tools,
        "list_reminders",
        lambda status="pending", limit=50: [
            {
                "id": 1,
                "title": "Leave early",
                "due_at": (tomorrow.replace(hour=8, minute=30, second=0, microsecond=0)).isoformat(),
                "recurrence": "once",
                "is_overdue": False,
            }
        ],
        raising=True,
    )

    reply = briefing_tools.build_morning_brief(day_offset=1)

    assert "Brief for" in reply
    assert "Tomorrow" in reply
    assert "Coffee" in reply
    assert "Leave early" in reply
