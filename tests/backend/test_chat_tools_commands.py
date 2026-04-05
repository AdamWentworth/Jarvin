from __future__ import annotations

import backend.agent.chat.chat_tool_helpers as chat_tool_helpers
import backend.agent.chat.assistant_chat_tools as chat_tools
from backend.agent.integration_facade import (
    CalendarAgendaResult,
    CalendarEventSummary,
    WebPageExtract,
    WebResearchResult,
    WebSearchItem,
)


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
        chat_tool_helpers,
        "browse_search_results",
        lambda query: WebResearchResult(
            provider="duckduckgo_lite",
            query=query,
            items=[WebSearchItem(title="Jarvin", url="https://example.com", snippet="Local assistant")],
            pages=[
                WebPageExtract(
                    url="https://example.com",
                    title="Jarvin",
                    excerpt="Jarvin is a local assistant focused on voice and tools.",
                )
            ],
        ),
        raising=True,
    )
    monkeypatch.setattr(chat_tool_helpers, "generate_reply", lambda *args, **kwargs: "- Jarvin is a local assistant [1].", raising=True)

    response = chat_tools.maybe_handle_tool_command("/tool web jarvin assistant")
    assert response.handled is True
    assert "duckduckgo_lite" in response.reply
    assert "https://example.com" in response.reply
    assert "local assistant [1]" in response.reply


def test_weather_command_formats_forecast(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "maybe_handle_weather_request",
        lambda text, conversation_id=None: type(
            "WeatherTool",
            (),
            {
                "reply": "Today in Seattle, Washington, United States: Partly cloudy. It is 58Â° right now.",
                "payload": {
                    "location_label": "Seattle, Washington, United States",
                    "summary": "Partly cloudy",
                    "icon_name": "cloud-sun",
                },
            },
        )(),
        raising=True,
    )

    response = chat_tools.maybe_handle_tool_command("/tool weather Seattle")
    assert response.handled is True
    assert "Seattle" in response.reply
    assert "Partly cloudy" in response.reply
    assert response.tool_kind == "weather"
    assert response.tool_payload["icon_name"] == "cloud-sun"


def test_brief_command_uses_briefing_tooling(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "handle_brief_command",
        lambda rest: f"Morning brief::{rest or 'default'}",
        raising=True,
    )

    response = chat_tools.maybe_handle_tool_command("/tool brief morning")
    assert response.handled is True
    assert "Morning brief::morning" in response.reply


def test_reminder_command_uses_reminder_tooling(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "handle_reminder_command",
        lambda rest: f"Saved reminder via command: {rest}",
        raising=True,
    )

    response = chat_tools.maybe_handle_tool_command("/tool reminder add call mom tomorrow at 5pm")
    assert response.handled is True
    assert "Saved reminder via command" in response.reply


def test_calendar_command_formats_agenda(monkeypatch):
    monkeypatch.setattr(chat_tool_helpers, "google_calendar_credentials_configured", lambda: True, raising=True)
    monkeypatch.setattr(chat_tool_helpers, "google_calendar_token_available", lambda: True, raising=True)
    monkeypatch.setattr(
        chat_tool_helpers,
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

