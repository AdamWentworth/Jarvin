from __future__ import annotations

from datetime import datetime, timedelta

import config as cfg
import backend.agent.reminders.reminder_request_planner as reminder_planner
from backend.agent.reminders.reminder_request_tools import handle_reminder_command, maybe_handle_reminder_request
import memory.reminders as reminders


def _use_temp_db(tmp_path) -> None:
    cfg.settings.data_dir = str(tmp_path)
    cfg.settings.db_filename = "reminder-tools-test.sqlite3"
    reminders._reset_for_tests()


def test_natural_language_can_create_reminder(tmp_path):
    _use_temp_db(tmp_path)
    try:
        reply = maybe_handle_reminder_request("Remind me to call mom in 30 minutes")
        items = reminders.list_reminders()

        assert reply is not None
        assert "Saved reminder `call mom`" in reply
        assert len(items) == 1
        assert items[0]["title"] == "call mom"
    finally:
        reminders._reset_for_tests()


def test_natural_language_can_create_weekday_routine(tmp_path):
    _use_temp_db(tmp_path)
    try:
        reply = maybe_handle_reminder_request("Every weekday at 8am remind me to stretch")
        items = reminders.list_reminders()

        assert reply is not None
        assert "repeat `weekday`" in reply
        assert items[0]["recurrence"] == "weekday"
    finally:
        reminders._reset_for_tests()


def test_natural_language_can_list_todays_reminders(tmp_path):
    _use_temp_db(tmp_path)
    try:
        # Keep the fixture on the current date even when this test runs near midnight.
        due_at = datetime.now().astimezone()
        reminders.create_reminder("Buy groceries", due_at=due_at)

        reply = maybe_handle_reminder_request("What do I need to do today?")

        assert reply is not None
        assert "Pending reminders for today" in reply
        assert "Buy groceries" in reply
    finally:
        reminders._reset_for_tests()


def test_natural_language_can_complete_recurring_reminder(tmp_path):
    _use_temp_db(tmp_path)
    try:
        reminders.create_reminder(
            "Stretch",
            due_at=datetime.now().astimezone() - timedelta(days=1),
            recurrence="daily",
        )

        reply = maybe_handle_reminder_request("mark stretch done")

        assert reply is not None
        assert "next `daily` reminder" in reply
    finally:
        reminders._reset_for_tests()


def test_explicit_reminder_command_can_delete(tmp_path):
    _use_temp_db(tmp_path)
    try:
        reminders.create_reminder("Pay rent", due_at=datetime.now().astimezone() + timedelta(days=1))

        reply = handle_reminder_command("delete Pay rent")
        items = reminders.list_reminders()

        assert "Deleted reminder `Pay rent`." == reply
        assert items == []
    finally:
        reminders._reset_for_tests()


def test_fuzzy_reminder_request_uses_llm_plan(tmp_path, monkeypatch):
    _use_temp_db(tmp_path)
    try:
        monkeypatch.setattr(
            reminder_planner,
            "generate_reply",
            lambda *args, **kwargs: (
                '{"is_reminder_request": true, "action": "create", "title": "call mom", '
                '"due_at_iso": "2026-04-04T13:00:00-07:00", "recurrence": "once"}'
            ),
            raising=True,
        )

        reply = maybe_handle_reminder_request("After lunch remind me to call mom", conversation_id=12)
        items = reminders.list_reminders()

        assert reply is not None
        assert "Saved reminder `call mom`" in reply
        assert len(items) == 1
        assert items[0]["title"] == "call mom"
    finally:
        reminders._reset_for_tests()
        reminder_planner.clear_reminder_context(12)


def test_missing_time_sets_follow_up_context(tmp_path, monkeypatch):
    _use_temp_db(tmp_path)
    try:
        monkeypatch.setattr(
            reminder_planner,
            "generate_reply",
            lambda *args, **kwargs: (
                '{"is_reminder_request": true, "action": "create", "title": "call mom", '
                '"due_at_iso": null, "when_text": null, "recurrence": "once"}'
            ),
            raising=True,
        )

        first_reply = maybe_handle_reminder_request("Remind me to call mom", conversation_id=33)
        second_reply = maybe_handle_reminder_request("tomorrow at 5pm", conversation_id=33)
        items = reminders.list_reminders()

        assert "What time should I set reminder `call mom` for?" in first_reply
        assert "Saved reminder `call mom`" in second_reply
        assert len(items) == 1
    finally:
        reminders._reset_for_tests()
        reminder_planner.clear_reminder_context(33)


def test_conflicting_due_at_iso_prefers_local_when_text(tmp_path, monkeypatch):
    _use_temp_db(tmp_path)
    try:
        monkeypatch.setattr(
            reminder_planner,
            "generate_reply",
            lambda *args, **kwargs: (
                '{"is_reminder_request": true, "action": "create", "title": "Go to Costco", '
                '"when_text": "tomorrow at 9am", "due_at_iso": "2026-04-27T09:00:00Z", "recurrence": "once"}'
            ),
            raising=True,
        )

        reply = maybe_handle_reminder_request(
            "Please make a reminder tomorrow at 9am to notify me on my phone to remind me to go to Costco at 12pm",
            conversation_id=34,
        )
        items = reminders.list_reminders()
        expected_due = (datetime.now().astimezone() + timedelta(days=1)).replace(
            hour=9,
            minute=0,
            second=0,
            microsecond=0,
        )
        actual_due = datetime.fromisoformat(items[0]["due_at"])

        assert reply == f"Saved reminder `Go to Costco` for `{expected_due:%Y-%m-%d %I:%M %p}`."
        assert len(items) == 1
        assert actual_due.date() == expected_due.date()
        assert (actual_due.hour, actual_due.minute) == (9, 0)
    finally:
        reminders._reset_for_tests()
        reminder_planner.clear_reminder_context(34)


def test_pronoun_move_uses_recent_reminder_context(tmp_path):
    _use_temp_db(tmp_path)
    try:
        reminders.create_reminder("Call mom", due_at=datetime.now().astimezone() + timedelta(hours=1))
        reminder_planner.remember_reminder_context(44, action="create", last_title="Call mom")

        reply = maybe_handle_reminder_request("move that to Friday afternoon", conversation_id=44)

        assert reply is not None
        assert "Moved `Call mom`" in reply
    finally:
        reminders._reset_for_tests()
        reminder_planner.clear_reminder_context(44)


def test_planned_update_action_reschedules_recent_reminder(tmp_path, monkeypatch):
    _use_temp_db(tmp_path)
    try:
        original_due = datetime.now().astimezone() + timedelta(days=1, hours=1)
        reminders.create_reminder("Call mom", due_at=original_due)
        reminder_planner.remember_reminder_context(45, action="create", last_title="Call mom")
        monkeypatch.setattr(
            reminder_planner,
            "generate_reply",
            lambda *args, **kwargs: (
                '{"is_reminder_request": true, "action": "update", "title": "Call mom", '
                '"when_text": "tomorrow at 9am", "due_at_iso": null, "recurrence": null}'
            ),
            raising=True,
        )

        reply = maybe_handle_reminder_request("update reminder to tomorrow at 9am", conversation_id=45)
        items = reminders.list_reminders(status="pending", limit=20)

        assert reply is not None
        assert "Moved `Call mom`" in reply
        assert len(items) == 1
    finally:
        reminders._reset_for_tests()
        reminder_planner.clear_reminder_context(45)


def test_planned_update_time_only_keeps_existing_reminder_date(tmp_path, monkeypatch):
    _use_temp_db(tmp_path)
    try:
        original_due = datetime.now().astimezone() + timedelta(days=1, hours=4)
        reminders.create_reminder("Go to Costco", due_at=original_due)
        reminder_planner.remember_reminder_context(46, action="list", last_title="Go to Costco", last_listed_ids=[1])
        monkeypatch.setattr(
            reminder_planner,
            "generate_reply",
            lambda *args, **kwargs: (
                '{"is_reminder_request": true, "action": "update", "title": "Go to Costco", '
                '"when_text": "9am", "due_at_iso": null, "recurrence": null}'
            ),
            raising=True,
        )

        reply = maybe_handle_reminder_request("update reminder to 9am", conversation_id=46)
        items = reminders.list_reminders(status="pending", limit=20)
        due_at = datetime.fromisoformat(items[0]["due_at"])

        assert reply is not None
        assert "Moved `Go to Costco`" in reply
        assert due_at.date() == original_due.date()
        assert due_at.hour == 9
        assert due_at.minute == 0
    finally:
        reminders._reset_for_tests()
        reminder_planner.clear_reminder_context(46)


def test_confirmation_style_time_update_moves_existing_reminder(tmp_path):
    _use_temp_db(tmp_path)
    try:
        original_due = datetime.now().astimezone() + timedelta(days=1, hours=4)
        reminders.create_reminder("Go to Costco", due_at=original_due)
        reminder_planner.remember_reminder_context(47, action="list", last_title="Go to Costco", last_listed_ids=[1])

        reply = maybe_handle_reminder_request(
            "Yes, that is the one. Please make sure that is at 9 a.m.",
            conversation_id=47,
        )
        items = reminders.list_reminders(status="pending", limit=20)
        due_at = datetime.fromisoformat(items[0]["due_at"])

        assert reply is not None
        assert "Moved `Go to Costco`" in reply
        assert due_at.date() == original_due.date()
        assert due_at.hour == 9
        assert len(items) == 1
    finally:
        reminders._reset_for_tests()
        reminder_planner.clear_reminder_context(47)


def test_additional_reminder_follow_up_reuses_current_title_and_date(tmp_path):
    _use_temp_db(tmp_path)
    try:
        original_due = datetime.now().astimezone() + timedelta(days=1, hours=4)
        created = reminders.create_reminder("Go to Costco", due_at=original_due)
        reminder_planner.remember_reminder_context(
            48,
            action="list",
            last_title="Go to Costco",
            last_due_at=created["due_at"],
            last_listed_ids=[int(created["id"])],
        )

        reply = maybe_handle_reminder_request(
            "Okay, for that one reminder, can you please remind me as well at 10 a.m.",
            conversation_id=48,
        )
        items = reminders.list_reminders(status="pending", limit=20)
        due_times = sorted(datetime.fromisoformat(item["due_at"]) for item in items)

        assert reply is not None
        assert "Saved reminder `Go to Costco`" in reply
        assert len(items) == 2
        assert due_times[0].date() == original_due.date()
        assert due_times[1].date() == original_due.date()
        assert {due.hour for due in due_times} == {10, original_due.hour}
    finally:
        reminders._reset_for_tests()
        reminder_planner.clear_reminder_context(48)


def test_correction_message_moves_recent_reminder_from_context(tmp_path):
    _use_temp_db(tmp_path)
    try:
        original_due = datetime.now().astimezone().replace(hour=9, minute=0, second=0, microsecond=0)
        created = reminders.create_reminder("Go to Costco", due_at=original_due)
        reminder_planner.remember_reminder_context(
            49,
            action="create",
            last_title="Go to Costco",
            last_due_at=created["due_at"],
            last_listed_ids=[int(created["id"])],
        )

        reply = maybe_handle_reminder_request(
            "Why did you save that for today at 9 a.m.? That's not right at all. Obviously, I meant 10 a.m. tomorrow.",
            conversation_id=49,
        )
        items = reminders.list_reminders(status="pending", limit=20)
        due_at = datetime.fromisoformat(items[0]["due_at"])

        assert reply is not None
        assert "Moved `Go to Costco`" in reply
        assert len(items) == 1
        assert due_at.hour == 10
        assert due_at.date() == (datetime.now().astimezone().date() + timedelta(days=1))
    finally:
        reminders._reset_for_tests()
        reminder_planner.clear_reminder_context(49)


def test_unknown_query_uses_single_recently_listed_reminder(tmp_path, monkeypatch):
    _use_temp_db(tmp_path)
    try:
        original_due = datetime.now().astimezone() + timedelta(days=1, hours=2)
        created = reminders.create_reminder("Go to Costco", due_at=original_due)
        reminder_planner.remember_reminder_context(
            50,
            action="list",
            last_title="Go to Costco",
            last_due_at=created["due_at"],
            last_listed_ids=[int(created["id"])],
        )
        monkeypatch.setattr(
            reminder_planner,
            "generate_reply",
            lambda *args, **kwargs: (
                '{"is_reminder_request": true, "action": "update", "query": "unknown", '
                '"when_text": "tomorrow at 10am", "due_at_iso": null, "recurrence": null}'
            ),
            raising=True,
        )

        reply = maybe_handle_reminder_request(
            "You already have the reminder, I'm just asking you to update the time.",
            conversation_id=50,
        )
        items = reminders.list_reminders(status="pending", limit=20)
        due_at = datetime.fromisoformat(items[0]["due_at"])

        assert reply is not None
        assert "Moved `Go to Costco`" in reply
        assert due_at.hour == 10
        assert len(items) == 1
    finally:
        reminders._reset_for_tests()
        reminder_planner.clear_reminder_context(50)


def test_recent_list_bulk_delete_removes_both_reminders(tmp_path):
    conversation_id = 55
    _use_temp_db(tmp_path)
    try:
        reminders.create_reminder("Hug a nest", due_at=datetime.now().astimezone() + timedelta(hours=1))
        reminders.create_reminder("Waken-ez", due_at=datetime.now().astimezone() + timedelta(hours=2))

        listed = maybe_handle_reminder_request("show me my reminders", conversation_id=conversation_id)
        deleted = maybe_handle_reminder_request("Remove the two reminders", conversation_id=conversation_id)
        items = reminders.list_reminders()

        assert listed is not None
        assert "Pending reminders for upcoming" in listed
        assert deleted == "Deleted 2 reminders: `Hug a nest`, `Waken-ez`."
        assert items == []
    finally:
        reminders._reset_for_tests()
        reminder_planner.clear_reminder_context(conversation_id)

