from __future__ import annotations

from datetime import datetime, timedelta

import config as cfg
from backend.agent.reminder_tools import handle_reminder_command, maybe_handle_reminder_request
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
        due_at = datetime.now().astimezone() + timedelta(hours=1)
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
