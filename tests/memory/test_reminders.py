from __future__ import annotations

from datetime import datetime, timedelta

import config as cfg
import memory.reminders as reminders


def _use_temp_db(tmp_path) -> None:
    cfg.settings.data_dir = str(tmp_path)
    cfg.settings.db_filename = "reminders-test.sqlite3"
    reminders._reset_for_tests()


def test_create_and_list_reminders(tmp_path):
    _use_temp_db(tmp_path)
    try:
        due_at = datetime.now().astimezone() + timedelta(hours=1)
        created = reminders.create_reminder("Call mom", due_at=due_at)

        items = reminders.list_reminders()

        assert created["title"] == "Call mom"
        assert created["status"] == "pending"
        assert len(items) == 1
        assert items[0]["title"] == "Call mom"
        assert items[0]["is_routine"] is False
    finally:
        reminders._reset_for_tests()


def test_complete_one_time_reminder_marks_done(tmp_path):
    _use_temp_db(tmp_path)
    try:
        due_at = datetime.now().astimezone() + timedelta(minutes=15)
        created = reminders.create_reminder("Take a break", due_at=due_at)

        completed = reminders.complete_reminder(int(created["id"]))

        assert completed["status"] == "done"
        assert completed["completed_at"]
    finally:
        reminders._reset_for_tests()


def test_complete_recurring_reminder_advances_due_date(tmp_path):
    _use_temp_db(tmp_path)
    try:
        due_at = datetime.now().astimezone() - timedelta(days=1)
        created = reminders.create_reminder("Stretch", due_at=due_at, recurrence="daily")

        completed = reminders.complete_reminder(int(created["id"]))

        assert completed["status"] == "pending"
        assert completed["recurrence"] == "daily"
        assert datetime.fromisoformat(completed["due_at"]) > datetime.now().astimezone()
    finally:
        reminders._reset_for_tests()
