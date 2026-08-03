from __future__ import annotations

from datetime import datetime, timedelta

import config as cfg
import backend.agent.chat.assistant_chat_tools as chat_tools
import backend.agent.chat.chat_compound_tool_requests as compound_tools
import backend.agent.chat.chat_followup_context as followup_context
import backend.agent.reminders.reminder_request_planner as reminder_planner
import memory.reminders as reminders


def _use_temp_db(tmp_path) -> None:
    cfg.settings.data_dir = str(tmp_path)
    cfg.settings.db_filename = "chat-compound-tools-test.sqlite3"
    reminders._reset_for_tests()


def test_compound_reminder_request_executes_delete_and_create(tmp_path, monkeypatch):
    conversation_id = 61
    _use_temp_db(tmp_path)
    try:
        reminders.create_reminder("Hug a nest", due_at=datetime.now().astimezone() + timedelta(hours=1))
        reminders.create_reminder("Waken-ez", due_at=datetime.now().astimezone() + timedelta(hours=2))

        listed = chat_tools.maybe_handle_assistant_tool_request(
            "Show me my reminders",
            conversation_id=conversation_id,
        )
        monkeypatch.setattr(
            compound_tools,
            "generate_reply",
            lambda *args, **kwargs: (
                '{"is_compound_request": true, "steps": ['
                '{"domain": "reminder", "prompt": "Remove the two reminders"}, '
                '{"domain": "reminder", "prompt": "Remind me to go to Costco at 12 to pick up equipment tomorrow at 9am"}'
                "]} "
            ),
            raising=True,
        )

        response = chat_tools.maybe_handle_assistant_tool_request(
            "Remove the two reminders and remind me at 9 a.m. tomorrow to go to Costco at 12 to pick up equipment.",
            conversation_id=conversation_id,
        )
        items = reminders.list_reminders()

        assert listed.handled is True
        assert response.handled is True
        assert "Deleted 2 reminders" in response.reply
        assert "Saved reminder `go to Costco at 12 to pick up equipment`" in response.reply
        assert len(items) == 1
        assert items[0]["title"] == "go to Costco at 12 to pick up equipment"
    finally:
        reminders._reset_for_tests()
        reminder_planner.clear_reminder_context(conversation_id)
        followup_context.clear_active_follow_up_domain(conversation_id)


def test_execute_compound_tool_steps_propagates_shared_date_hint_to_reminder():
    seen_prompts = []

    response = compound_tools.execute_compound_tool_steps(
        (
            compound_tools.CompoundToolStep(domain="calendar", prompt="Please make an event to go to Costco tomorrow at 12 noon"),
            compound_tools.CompoundToolStep(domain="reminder", prompt="Please make a reminder at 9am to notify me on my phone to remind me to go to Costco at 12pm"),
        ),
        source_text=(
            "Please make me an event to go to Costco tomorrow at 12 noon. "
            "And then, in a separate thing, please make a reminder at 9am to remind me to go to Costco at 12pm."
        ),
        conversation_id=88,
        ToolChatResponse=chat_tools.ToolChatResponse,
        maybe_handle_reminder_request=lambda text, conversation_id=None: seen_prompts.append(text) or "Saved reminder `Go to Costco` for `tomorrow at 9am`.",
        maybe_calendar_tool_response=lambda text, conversation_id=None: chat_tools.ToolChatResponse(
            handled=True,
            reply="Created `going to Costco` on your calendar for `tomorrow at noon`.",
            active_domain="calendar",
        ),
    )

    assert response.handled is True
    assert seen_prompts == [
        "Please make a reminder tomorrow at 9am to notify me on my phone to remind me to go to Costco at 12pm"
    ]
