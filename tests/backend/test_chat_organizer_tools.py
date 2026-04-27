from __future__ import annotations

from datetime import datetime, timedelta

import config as cfg
import backend.agent.chat.assistant_chat_tools as chat_tools
import backend.agent.chat.chat_followup_context as followup_context
import backend.agent.chat.chat_organizer_tools as organizer_tools
import memory.calendar_events as calendar_events
import memory.reminders as reminders


def _use_temp_db(tmp_path) -> None:
    cfg.settings.data_dir = str(tmp_path)
    cfg.settings.db_filename = "chat-organizer-tools-test.sqlite3"
    reminders._reset_for_tests()
    calendar_events._reset_for_tests()


def test_combined_overview_lists_events_and_reminders(tmp_path):
    conversation_id = 71
    _use_temp_db(tmp_path)
    try:
        reminders.create_reminder("Call mom", due_at=datetime.now().astimezone() + timedelta(hours=1))
        start = datetime.now().astimezone() + timedelta(hours=2)
        calendar_events.create_calendar_event(
            "Lunch with Sam",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
        )

        response = chat_tools.maybe_handle_assistant_tool_request(
            "Could you output all of my current events and reminders for a quick overview?",
            conversation_id=conversation_id,
        )

        assert response.handled is True
        assert "Current overview:" in response.reply
        assert "Calendar events:" in response.reply
        assert "Lunch with Sam" in response.reply
        assert "Reminders:" in response.reply
        assert "Call mom" in response.reply
    finally:
        reminders._reset_for_tests()
        calendar_events._reset_for_tests()
        followup_context.clear_active_follow_up_domain(conversation_id)


def test_cleanup_request_keeps_selected_items_and_deletes_rest(tmp_path, monkeypatch):
    conversation_id = 72
    _use_temp_db(tmp_path)
    try:
        keep_reminder = reminders.create_reminder("Go to Costco", due_at=datetime.now().astimezone() + timedelta(hours=1))
        drop_reminder = reminders.create_reminder("Old reminder", due_at=datetime.now().astimezone() + timedelta(hours=2))
        keep_start = datetime.now().astimezone() + timedelta(hours=3)
        keep_event = calendar_events.create_calendar_event(
            "Appointment to go to Costco",
            starts_at=keep_start,
            ends_at=keep_start + timedelta(hours=1),
        )
        drop_start = datetime.now().astimezone() + timedelta(hours=5)
        calendar_events.create_calendar_event(
            "Duplicate Costco event",
            starts_at=drop_start,
            ends_at=drop_start + timedelta(hours=1),
        )

        monkeypatch.setattr(
            organizer_tools,
            "generate_reply",
            lambda *args, **kwargs: (
                "{"
                f"\"keep_reminder_ids\": [{int(keep_reminder['id'])}], "
                f"\"keep_calendar_event_ids\": [{int(keep_event['id'])}]"
                "}"
            ),
            raising=True,
        )

        staged = chat_tools.maybe_handle_assistant_tool_request(
            "Keep only two items. One is the reminder to go to Costco and the other is the appointment to go to Costco. Everything else, get rid of it.",
            conversation_id=conversation_id,
        )
        confirmed = chat_tools.maybe_handle_assistant_tool_request(
            "yes",
            conversation_id=conversation_id,
        )

        remaining_reminders = reminders.list_reminders(status="pending", limit=20)
        remaining_events = calendar_events.list_calendar_events(limit=20)

        assert staged.handled is True
        assert "Reply `yes` to confirm" in staged.reply
        assert "Old reminder" in staged.reply
        assert "Duplicate Costco event" in staged.reply

        assert confirmed.handled is True
        assert "Kept:" in confirmed.reply
        assert "Deleted:" in confirmed.reply
        assert [item["title"] for item in remaining_reminders] == ["Go to Costco"]
        assert [item["title"] for item in remaining_events] == ["Appointment to go to Costco"]
    finally:
        reminders._reset_for_tests()
        calendar_events._reset_for_tests()
        followup_context.clear_active_follow_up_domain(conversation_id)


def test_organizer_delete_all_follow_up_clears_everything(tmp_path):
    conversation_id = 73
    _use_temp_db(tmp_path)
    try:
        reminders.create_reminder("Go to Costco", due_at=datetime.now().astimezone() + timedelta(hours=1))
        start = datetime.now().astimezone() + timedelta(hours=2)
        calendar_events.create_calendar_event(
            "Appointment to go to Costco",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
        )

        reminder_overview = chat_tools.maybe_handle_assistant_tool_request(
            "Show me my reminders.",
            conversation_id=conversation_id,
        )
        organizer_overview = chat_tools.maybe_handle_assistant_tool_request(
            "Please output all of my calendar events, announcements, appointments, reminders, all of it.",
            conversation_id=conversation_id,
        )
        staged = chat_tools.maybe_handle_assistant_tool_request(
            "All of them.",
            conversation_id=conversation_id,
        )
        confirmed = chat_tools.maybe_handle_assistant_tool_request(
            "Yes, that would be perfect. I want a clean slate.",
            conversation_id=conversation_id,
        )

        remaining_reminders = reminders.list_reminders(status="pending", limit=20)
        remaining_events = calendar_events.list_calendar_events(limit=20)

        assert reminder_overview.handled is True
        assert reminder_overview.active_domain == "reminder"

        assert organizer_overview.handled is True
        assert organizer_overview.active_domain == "organizer"
        assert "Current overview:" in organizer_overview.reply

        assert staged.handled is True
        assert staged.active_domain == "organizer"
        assert "I can delete these items:" in staged.reply
        assert "Reply `yes` to confirm" in staged.reply

        assert confirmed.handled is True
        assert "Deleted:" in confirmed.reply
        assert remaining_reminders == []
        assert remaining_events == []
    finally:
        reminders._reset_for_tests()
        calendar_events._reset_for_tests()
        followup_context.clear_active_follow_up_domain(conversation_id)


def test_organizer_delete_all_calendar_events_keeps_reminders(tmp_path):
    conversation_id = 74
    _use_temp_db(tmp_path)
    try:
        reminders.create_reminder("Keep reminder", due_at=datetime.now().astimezone() + timedelta(hours=1))
        start = datetime.now().astimezone() + timedelta(hours=2)
        calendar_events.create_calendar_event(
            "Delete this event",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
        )

        staged = chat_tools.maybe_handle_assistant_tool_request(
            "Okay, good. Now let's delete all my calendar events please.",
            conversation_id=conversation_id,
        )
        confirmed = chat_tools.maybe_handle_assistant_tool_request(
            "yes",
            conversation_id=conversation_id,
        )

        remaining_reminders = reminders.list_reminders(status="pending", limit=20)
        remaining_events = calendar_events.list_calendar_events(limit=20)

        assert staged.handled is True
        assert staged.active_domain == "organizer"
        assert "Keep reminder" in staged.reply
        assert "Delete this event" in staged.reply

        assert confirmed.handled is True
        assert [item["title"] for item in remaining_reminders] == ["Keep reminder"]
        assert remaining_events == []
    finally:
        reminders._reset_for_tests()
        calendar_events._reset_for_tests()
        followup_context.clear_active_follow_up_domain(conversation_id)
