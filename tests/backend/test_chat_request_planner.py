from __future__ import annotations

from backend.agent.chat import chat_request_planner as planner


def test_top_level_request_planner_parses_organizer_route(monkeypatch):
    monkeypatch.setattr(
        planner,
        "generate_reply",
        lambda *args, **kwargs: (
            '{"is_tool_request": true, "domain": "organizer", '
            '"normalized_request": "show all my calendar events and reminders", '
            '"confidence": "high", "reason": "Combined overview request.", "steps": []}'
        ),
        raising=True,
    )

    plan = planner.maybe_plan_tool_request_route(
        "Could you show me everything in my schedule and reminders?"
    )

    assert plan is not None
    assert plan.domain == "organizer"
    assert plan.normalized_request == "show all my calendar events and reminders"
    assert plan.confidence == "high"


def test_top_level_request_planner_parses_compound_steps(monkeypatch):
    monkeypatch.setattr(
        planner,
        "generate_reply",
        lambda *args, **kwargs: (
            '{"is_tool_request": true, "domain": "compound", "normalized_request": null, '
            '"confidence": "high", "reason": "Two actions.", "steps": ['
            '{"domain": "reminder", "prompt": "delete all reminders"}, '
            '{"domain": "calendar", "prompt": "delete all my calendar events"}]}'
        ),
        raising=True,
    )

    plan = planner.maybe_plan_tool_request_route(
        "Delete all my reminders and calendar events."
    )

    assert plan is not None
    assert plan.domain == "compound"
    assert len(plan.steps) == 2
    assert plan.steps[0].domain == "reminder"
    assert plan.steps[1].prompt == "delete all my calendar events"


def test_top_level_request_planner_coerces_calendar_plus_steps_to_compound(monkeypatch):
    monkeypatch.setattr(
        planner,
        "generate_reply",
        lambda *args, **kwargs: (
            '{"is_tool_request": true, "domain": "calendar", '
            '"normalized_request": "create an event and add a reminder", '
            '"confidence": "high", "reason": "Two actions.", "steps": ['
            '{"domain": "calendar", "prompt": "create an event tomorrow at noon"}, '
            '{"domain": "reminder", "prompt": "add a reminder at 9am"}]}'
        ),
        raising=True,
    )

    plan = planner.maybe_plan_tool_request_route(
        "Please create an event tomorrow at noon and add a reminder at 9am."
    )

    assert plan is not None
    assert plan.domain == "compound"
    assert len(plan.steps) == 2


def test_top_level_request_planner_forces_combined_overview_to_organizer(monkeypatch):
    monkeypatch.setattr(
        planner,
        "generate_reply",
        lambda *args, **kwargs: (
            '{"is_tool_request": true, "domain": "reminder", '
            '"normalized_request": "show all reminders and events", '
            '"confidence": "high", "reason": "Overview request.", "steps": []}'
        ),
        raising=True,
    )

    plan = planner.maybe_plan_tool_request_route(
        "Can you please show me all reminders we currently have and all events we currently have?"
    )

    assert plan is not None
    assert plan.domain == "organizer"
