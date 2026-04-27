from __future__ import annotations

from datetime import datetime, timedelta

import config as cfg
import backend.agent.calendar.calendar_integration_service as calendar_service
import memory.calendar_events as calendar_events


def _use_temp_db(tmp_path) -> None:
    cfg.settings.data_dir = str(tmp_path)
    cfg.settings.db_filename = "calendar-test.sqlite3"
    calendar_events._reset_for_tests()


def test_begin_calendar_setup_reports_local_storage(tmp_path):
    _use_temp_db(tmp_path)
    try:
        reply = calendar_service.begin_calendar_setup()

        assert "built-in calendar is ready" in reply
        assert "calendar_events" in reply
        assert "no Google account" in reply
    finally:
        calendar_events._reset_for_tests()


def test_calendar_agenda_expands_recurring_events(tmp_path):
    _use_temp_db(tmp_path)
    try:
        now = datetime.now().astimezone()
        days_until_saturday = (5 - now.weekday()) % 7
        first_start = (now + timedelta(days=days_until_saturday)).replace(hour=9, minute=0, second=0, microsecond=0)
        first_end = first_start + timedelta(hours=1)

        calendar_events.create_calendar_event(
            "Project sync",
            starts_at=first_start,
            ends_at=first_end,
            recurrence="weekly:saturday",
            location="Office",
        )

        agenda = calendar_service.get_calendar_agenda(window_days=14)
        matching = [item for item in agenda.events if item.title == "Project sync"]

        assert agenda.calendar_id == "Jarvin Calendar"
        assert len(matching) >= 2
        assert matching[0].location == "Office"
    finally:
        calendar_events._reset_for_tests()


def test_create_calendar_event_from_text_saves_local_event(tmp_path):
    _use_temp_db(tmp_path)
    try:
        summary = calendar_service.create_calendar_event_from_text("Lunch with Sam tomorrow at noon")
        matches = calendar_service.find_calendar_events("Lunch with Sam", window_days=7, max_results=5)

        assert summary.title == "Lunch with Sam"
        assert matches
        assert matches[0].title == "Lunch with Sam"
    finally:
        calendar_events._reset_for_tests()
