from __future__ import annotations

import backend.agent.chat_tools as chat_tools
from backend.agent.external_tools import CalendarAgendaResult, CalendarEventSummary, WeatherResult, WebSearchItem, WebSearchResult


def test_help_command_includes_external_tools(monkeypatch):
    monkeypatch.setattr(
        chat_tools.tools,
        "manifest",
        lambda: {
            "enabled": True,
            "workspace_root": "D:/Projects/Jarvin",
            "commands": ["/tool web <query>", "/tool weather <location>", "/tool calendar [days]"],
            "allowed_commands": ["git status"],
            "writes_enabled": True,
            "commands_enabled": True,
        },
        raising=True,
    )

    response = chat_tools.maybe_handle_tool_command("/tool help")
    assert response.handled is True
    assert "/tool weather <location>" in response.reply


def test_web_command_formats_results(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "search_web",
        lambda query: WebSearchResult(
            provider="duckduckgo_lite",
            query=query,
            items=[WebSearchItem(title="Jarvin", url="https://example.com", snippet="Local assistant")],
        ),
        raising=True,
    )

    response = chat_tools.maybe_handle_tool_command("/tool web jarvin assistant")
    assert response.handled is True
    assert "duckduckgo_lite" in response.reply
    assert "https://example.com" in response.reply


def test_weather_command_formats_forecast(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "get_weather",
        lambda location: WeatherResult(
            location_label="Seattle, Washington, United States",
            forecast_summary="Partly cloudy",
            temperature="58°",
            feels_like="56°",
            wind="8 mph",
            daily_outlook="High 61°, low 49°, precip 20%",
        ),
        raising=True,
    )

    response = chat_tools.maybe_handle_tool_command("/tool weather Seattle")
    assert response.handled is True
    assert "Seattle" in response.reply
    assert "Partly cloudy" in response.reply


def test_calendar_command_formats_agenda(monkeypatch):
    monkeypatch.setattr(chat_tools, "google_calendar_credentials_configured", lambda: True, raising=True)
    monkeypatch.setattr(chat_tools, "google_calendar_token_available", lambda: True, raising=True)
    monkeypatch.setattr(
        chat_tools,
        "get_calendar_agenda",
        lambda window_days=7: CalendarAgendaResult(
            calendar_id="primary",
            window_days=window_days,
            events=[
                CalendarEventSummary(
                    starts_at="2026-04-04 09:00 AM",
                    title="Morning standup",
                    location="Home office",
                )
            ],
        ),
        raising=True,
    )

    response = chat_tools.maybe_handle_tool_command("/tool calendar 3")
    assert response.handled is True
    assert "Morning standup" in response.reply
    assert "3 day(s)" in response.reply


def test_google_command_warns_when_provider_is_not_google(monkeypatch):
    monkeypatch.setattr(chat_tools.cfg.settings, "agent_web_search_provider", "duckduckgo_lite", raising=False)

    response = chat_tools.maybe_handle_tool_command("/tool google jarvin")
    assert response.handled is True
    assert "not the active provider" in response.reply


def test_natural_language_weather_request_is_handled(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "get_weather",
        lambda location: WeatherResult(
            location_label="Seattle, Washington, United States",
            forecast_summary="Clear sky",
            temperature="46°",
            feels_like="43°",
            wind="3 mph",
            daily_outlook="High 52°, low 40°, precip 0%",
        ),
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request("What's the weather in Seattle?")
    assert response.handled is True
    assert "Clear sky" in response.reply


def test_natural_language_calendar_request_reports_missing_setup(monkeypatch):
    monkeypatch.setattr(chat_tools, "google_calendar_credentials_configured", lambda: False, raising=True)

    response = chat_tools.maybe_handle_assistant_tool_request("What's on my calendar tomorrow?")
    assert response.handled is True
    assert "OAuth credentials" in response.reply


def test_natural_language_google_request_falls_back_when_google_is_not_configured(monkeypatch):
    monkeypatch.setattr(chat_tools.cfg.settings, "agent_web_search_provider", "duckduckgo_lite", raising=False)
    monkeypatch.setattr(chat_tools, "google_search_is_configured", lambda: False, raising=True)
    monkeypatch.setattr(
        chat_tools,
        "search_web",
        lambda query: WebSearchResult(
            provider="duckduckgo_lite",
            query=query,
            items=[WebSearchItem(title="Jarvin docs", url="https://example.com", snippet="Search result")],
        ),
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request("Google Jarvin docs")
    assert response.handled is True
    assert "not configured on this host" in response.reply
    assert "https://example.com" in response.reply


def test_natural_language_repo_search_is_handled(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "_repo_search_reply",
        lambda query: f"Search results for `{query}`:\n- `backend/api/app.py:1` include_router(...)",
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request("search the repo for include_router")
    assert response.handled is True
    assert "include_router" in response.reply


def test_natural_language_run_is_handled(monkeypatch):
    monkeypatch.setattr(chat_tools, "_run_reply", lambda command: f"Command `{command}` exited with `0`.", raising=True)

    response = chat_tools.maybe_handle_assistant_tool_request("run git status")
    assert response.handled is True
    assert "git status" in response.reply
