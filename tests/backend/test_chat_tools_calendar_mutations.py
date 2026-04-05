from __future__ import annotations

import backend.agent.chat.chat_tool_helpers as chat_tool_helpers
import backend.agent.chat.assistant_chat_tools as chat_tools
from backend.agent.integration_facade import CalendarEventDetails, CalendarEventMatch, CalendarEventSummary
from backend.agent.calendar_pending_actions import clear_pending_calendar_action


def test_natural_language_calendar_delete_requires_confirmation(monkeypatch):
    conversation_id = 12
    clear_pending_calendar_action(conversation_id)

    monkeypatch.setattr(
        chat_tool_helpers,
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
        chat_tool_helpers,
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
        chat_tool_helpers,
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
        chat_tool_helpers,
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
        chat_tool_helpers,
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
        chat_tool_helpers,
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
        chat_tool_helpers,
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


def test_fuzzy_calendar_reschedule_phrase_is_handled(monkeypatch):
    conversation_id = 15
    clear_pending_calendar_action(conversation_id)

    monkeypatch.setattr(
        chat_tool_helpers,
        "find_calendar_events",
        lambda query: [
            CalendarEventMatch(
                event_id="evt-4",
                title="Project sync",
                starts_at="2026-04-07T13:00:00-07:00",
                ends_at="2026-04-07T14:00:00-07:00",
                location="Conference room",
            )
        ],
        raising=True,
    )
    monkeypatch.setattr(
        chat_tool_helpers,
        "prepare_reschedule_times",
        lambda event, when_text: ("2026-04-07T14:00:00-07:00", "2026-04-07T15:00:00-07:00"),
        raising=True,
    )

    try:
        response = chat_tools.maybe_handle_assistant_tool_request(
            "Shift project sync back an hour on my calendar",
            conversation_id=conversation_id,
        )

        assert response.handled is True
        assert "Reply `yes` to move it" in response.reply
    finally:
        clear_pending_calendar_action(conversation_id)


def test_contextual_calendar_location_follow_up_is_handled(monkeypatch):
    conversation_id = 16
    clear_pending_calendar_action(conversation_id)
    chat_tools.maybe_plan_calendar_request("Show event details for project sync on my calendar", conversation_id=conversation_id)

    monkeypatch.setattr(
        chat_tool_helpers,
        "find_calendar_events",
        lambda query: [
            CalendarEventMatch(
                event_id="evt-5",
                title="Project sync",
                starts_at="2026-04-07T13:00:00-07:00",
                ends_at="2026-04-07T14:00:00-07:00",
                location="Conference room",
            )
        ],
        raising=True,
    )

    try:
        response = chat_tools.maybe_handle_assistant_tool_request(
            "Make Zoom the location for that meeting",
            conversation_id=conversation_id,
        )

        assert response.handled is True
        assert "location -> `Zoom`" in response.reply
    finally:
        clear_pending_calendar_action(conversation_id)

