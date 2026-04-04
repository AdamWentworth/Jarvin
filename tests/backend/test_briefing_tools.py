from __future__ import annotations

from datetime import datetime, timedelta

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
        lambda location_hint=None: f"brief::{location_hint or 'default'}",
        raising=True,
    )

    reply = briefing_tools.maybe_handle_brief_request("Give me my morning brief for Portland")

    assert reply == "brief::Portland"


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
    assert "nothing due today" in reply
