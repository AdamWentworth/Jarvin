from __future__ import annotations

import backend.agent.reminders.reminder_request_planner as reminder_planner


def test_awaiting_time_follow_up_uses_context():
    reminder_planner.remember_reminder_context(
        101,
        action="awaiting_time",
        last_title="call mom",
        awaiting_time_title="call mom",
        awaiting_time_recurrence="once",
    )
    try:
        plan = reminder_planner.maybe_plan_reminder_request("tomorrow at 5pm", conversation_id=101)

        assert plan is not None
        assert plan.action == "create"
        assert plan.title == "call mom"
        assert plan.when_text == "tomorrow at 5pm"
    finally:
        reminder_planner.clear_reminder_context(101)


def test_pronoun_move_uses_recent_title():
    reminder_planner.remember_reminder_context(202, action="create", last_title="Call mom")
    try:
        plan = reminder_planner.maybe_plan_reminder_request("move that to Friday afternoon", conversation_id=202)

        assert plan is not None
        assert plan.action == "move"
        assert plan.query == "Call mom"
        assert plan.when_text == "Friday afternoon"
    finally:
        reminder_planner.clear_reminder_context(202)


def test_llm_plan_can_normalize_fuzzy_reminder(monkeypatch):
    monkeypatch.setattr(
        reminder_planner,
        "generate_reply",
        lambda *args, **kwargs: (
            '{"is_reminder_request": true, "action": "create", "title": "call mom", '
            '"due_at_iso": "2026-04-04T13:00:00-07:00", "recurrence": "once"}'
        ),
        raising=True,
    )

    plan = reminder_planner.maybe_plan_reminder_request("after lunch remind me to call mom", conversation_id=303)

    assert plan is not None
    assert plan.action == "create"
    assert plan.title == "call mom"
    assert plan.due_at_iso == "2026-04-04T13:00:00-07:00"

