from __future__ import annotations

import backend.agent.chat_tools as chat_tools
from backend.agent.external_tools import (
    CalendarAgendaResult,
    CalendarEventDetails,
    CalendarEventMatch,
    CalendarEventSummary,
    WeatherResult,
    WebSearchItem,
    WebSearchResult,
)
from backend.agent.pending_actions import clear_pending_calendar_action


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


def test_natural_language_calendar_create_is_handled(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "create_calendar_event_from_text",
        lambda details: CalendarEventSummary(
            starts_at="2026-04-04 12:00 PM",
            title="Lunch with Sam",
            location="Cafe Vita",
        ),
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request(
        "Schedule lunch with Sam tomorrow at noon on my calendar"
    )

    assert response.handled is True
    assert "Created `Lunch with Sam`" in response.reply
    assert "Cafe Vita" in response.reply


def test_natural_language_calendar_details_are_returned(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "find_calendar_events",
        lambda query: [
            CalendarEventMatch(
                event_id="evt-0",
                title="Lunch with Sam",
                starts_at="2026-04-05T12:00:00-07:00",
                ends_at="2026-04-05T13:00:00-07:00",
                location="Cafe Vita",
                description="Bring the project notes.",
            )
        ],
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "get_calendar_event_details",
        lambda event_id: CalendarEventDetails(
            event_id=event_id,
            calendar_id="primary",
            starts_at="2026-04-05 12:00 PM",
            ends_at="2026-04-05 01:00 PM",
            title="Lunch with Sam",
            location="Cafe Vita",
            description="Bring the project notes.",
        ),
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request("Show event details for lunch with Sam on my calendar")

    assert response.handled is True
    assert "Details for `Lunch with Sam`" in response.reply
    assert "Bring the project notes." in response.reply


def test_natural_language_calendar_delete_requires_confirmation(monkeypatch):
    conversation_id = 12
    clear_pending_calendar_action(conversation_id)

    monkeypatch.setattr(
        chat_tools,
        "find_calendar_events",
        lambda query: [
            CalendarEventMatch(
                event_id="evt-1",
                title="Dentist appointment",
                starts_at="2026-04-05T14:00:00-07:00",
                ends_at="2026-04-05T15:00:00-07:00",
                location="Dental office",
            )
        ],
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "delete_calendar_event",
        lambda event_id: CalendarEventSummary(
            starts_at="2026-04-05 02:00 PM",
            title="Dentist appointment",
            location="Dental office",
        ),
        raising=True,
    )

    try:
        response = chat_tools.maybe_handle_assistant_tool_request(
            "Delete dentist appointment from my calendar",
            conversation_id=conversation_id,
        )
        assert response.handled is True
        assert "Reply `yes` to confirm deleting it" in response.reply

        confirmed = chat_tools.maybe_handle_assistant_tool_request(
            "yes",
            conversation_id=conversation_id,
        )
        assert confirmed.handled is True
        assert "Deleted `Dentist appointment`" in confirmed.reply
    finally:
        clear_pending_calendar_action(conversation_id)


def test_natural_language_calendar_rename_requires_confirmation(monkeypatch):
    conversation_id = 21
    clear_pending_calendar_action(conversation_id)

    monkeypatch.setattr(
        chat_tools,
        "find_calendar_events",
        lambda query: [
            CalendarEventMatch(
                event_id="evt-rename",
                title="Lunch with Sam",
                starts_at="2026-04-05T12:00:00-07:00",
                ends_at="2026-04-05T13:00:00-07:00",
                location="Cafe Vita",
            )
        ],
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "update_calendar_event_fields",
        lambda event_id, title=None, location=None, description=None: CalendarEventDetails(
            event_id=event_id,
            calendar_id="primary",
            starts_at="2026-04-05 12:00 PM",
            ends_at="2026-04-05 01:00 PM",
            title=title or "Lunch with Sam",
            location=location or "Cafe Vita",
            description=description or "",
        ),
        raising=True,
    )

    try:
        response = chat_tools.maybe_handle_assistant_tool_request(
            "Rename lunch with Sam to brunch with Sam on my calendar",
            conversation_id=conversation_id,
        )
        assert response.handled is True
        assert "title -> `brunch with Sam on my calendar`" not in response.reply
        assert "title -> `brunch with Sam`" in response.reply

        confirmed = chat_tools.maybe_handle_assistant_tool_request(
            "yes",
            conversation_id=conversation_id,
        )
        assert confirmed.handled is True
        assert "Updated `brunch with Sam` on your calendar." in confirmed.reply
    finally:
        clear_pending_calendar_action(conversation_id)


def test_natural_language_calendar_location_update_requires_confirmation(monkeypatch):
    conversation_id = 22
    clear_pending_calendar_action(conversation_id)

    monkeypatch.setattr(
        chat_tools,
        "find_calendar_events",
        lambda query: [
            CalendarEventMatch(
                event_id="evt-location",
                title="Project sync",
                starts_at="2026-04-07T13:00:00-07:00",
                ends_at="2026-04-07T14:00:00-07:00",
                location="Conference room",
            )
        ],
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "update_calendar_event_fields",
        lambda event_id, title=None, location=None, description=None: CalendarEventDetails(
            event_id=event_id,
            calendar_id="primary",
            starts_at="2026-04-07 01:00 PM",
            ends_at="2026-04-07 02:00 PM",
            title="Project sync",
            location=location if location is not None else "Conference room",
            description=description or "",
        ),
        raising=True,
    )

    try:
        response = chat_tools.maybe_handle_assistant_tool_request(
            "Change the location of project sync to Zoom on my calendar",
            conversation_id=conversation_id,
        )
        assert response.handled is True
        assert "location -> `Zoom`" in response.reply

        confirmed = chat_tools.maybe_handle_assistant_tool_request(
            "yes",
            conversation_id=conversation_id,
        )
        assert confirmed.handled is True
        assert "Location: `Zoom`." in confirmed.reply
    finally:
        clear_pending_calendar_action(conversation_id)


def test_natural_language_calendar_notes_update_requires_confirmation(monkeypatch):
    conversation_id = 23
    clear_pending_calendar_action(conversation_id)

    monkeypatch.setattr(
        chat_tools,
        "find_calendar_events",
        lambda query: [
            CalendarEventMatch(
                event_id="evt-notes",
                title="Doctor visit",
                starts_at="2026-04-09T09:00:00-07:00",
                ends_at="2026-04-09T10:00:00-07:00",
                location="Clinic",
            )
        ],
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "update_calendar_event_fields",
        lambda event_id, title=None, location=None, description=None: CalendarEventDetails(
            event_id=event_id,
            calendar_id="primary",
            starts_at="2026-04-09 09:00 AM",
            ends_at="2026-04-09 10:00 AM",
            title="Doctor visit",
            location="Clinic",
            description=description or "",
        ),
        raising=True,
    )

    try:
        response = chat_tools.maybe_handle_assistant_tool_request(
            "Update the notes for doctor visit to bring insurance card on my calendar",
            conversation_id=conversation_id,
        )
        assert response.handled is True
        assert "notes updated" in response.reply

        confirmed = chat_tools.maybe_handle_assistant_tool_request(
            "yes",
            conversation_id=conversation_id,
        )
        assert confirmed.handled is True
        assert "bring insurance card" in confirmed.reply
    finally:
        clear_pending_calendar_action(conversation_id)


def test_natural_language_calendar_delete_can_be_canceled(monkeypatch):
    conversation_id = 13
    clear_pending_calendar_action(conversation_id)

    monkeypatch.setattr(
        chat_tools,
        "find_calendar_events",
        lambda query: [
            CalendarEventMatch(
                event_id="evt-2",
                title="Design review",
                starts_at="2026-04-06T09:00:00-07:00",
                ends_at="2026-04-06T10:00:00-07:00",
                location="Zoom",
            )
        ],
        raising=True,
    )

    try:
        response = chat_tools.maybe_handle_assistant_tool_request(
            "Cancel design review from my calendar",
            conversation_id=conversation_id,
        )
        assert response.handled is True

        canceled = chat_tools.maybe_handle_assistant_tool_request(
            "cancel",
            conversation_id=conversation_id,
        )
        assert canceled.handled is True
        assert "canceled that pending calendar change" in canceled.reply
    finally:
        clear_pending_calendar_action(conversation_id)


def test_natural_language_calendar_reschedule_requires_confirmation(monkeypatch):
    conversation_id = 14
    clear_pending_calendar_action(conversation_id)

    monkeypatch.setattr(
        chat_tools,
        "find_calendar_events",
        lambda query: [
            CalendarEventMatch(
                event_id="evt-3",
                title="Project sync",
                starts_at="2026-04-07T13:00:00-07:00",
                ends_at="2026-04-07T14:00:00-07:00",
                location="Conference room",
            )
        ],
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "prepare_reschedule_times",
        lambda event, when_text: ("2026-04-08T15:30:00-07:00", "2026-04-08T16:30:00-07:00"),
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "reschedule_calendar_event",
        lambda event_id, new_start_iso, new_end_iso: CalendarEventSummary(
            starts_at="2026-04-08 03:30 PM",
            title="Project sync",
            location="Conference room",
        ),
        raising=True,
    )

    try:
        response = chat_tools.maybe_handle_assistant_tool_request(
            "Move project sync to tomorrow at 3:30pm on my calendar",
            conversation_id=conversation_id,
        )
        assert response.handled is True
        assert "Reply `yes` to move it" in response.reply

        confirmed = chat_tools.maybe_handle_assistant_tool_request(
            "yes",
            conversation_id=conversation_id,
        )
        assert confirmed.handled is True
        assert "Rescheduled `Project sync`" in confirmed.reply
    finally:
        clear_pending_calendar_action(conversation_id)
