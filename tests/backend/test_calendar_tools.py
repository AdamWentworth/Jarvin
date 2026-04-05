from __future__ import annotations

import backend.agent.calendar.calendar_request_tools as calendar_tools


def test_calendar_planner_handles_look_at_my_calendar_today():
    plan = calendar_tools.maybe_plan_calendar_request(
        "Hey Jarvan, can you look at my calendar for today and let me know what I have going on?",
        conversation_id=201,
    )

    assert plan is not None
    assert plan.is_calendar_request is True
    assert plan.action == "lookup"
    assert plan.window_days == 1


def test_calendar_planner_handles_google_calendar_phrase_as_calendar():
    plan = calendar_tools.maybe_plan_calendar_request(
        "Please just look at my Google Calendar and tell me what I have this week.",
        conversation_id=202,
    )

    assert plan is not None
    assert plan.is_calendar_request is True
    assert plan.action == "lookup"
    assert plan.window_days == 7


def test_calendar_planner_uses_recent_context_for_follow_up():
    calendar_tools._calendar_context["203"] = calendar_tools.CalendarConversationContext(last_action="lookup")

    plan = calendar_tools.maybe_plan_calendar_request(
        "How about instead if you just look at all the events for the upcoming week and give me anything that's actually real",
        conversation_id=203,
    )

    assert plan is not None
    assert plan.is_calendar_request is True
    assert plan.action == "lookup"
    assert plan.window_days == 7


def test_calendar_planner_can_fall_back_to_llm_for_fuzzier_calendar_request(monkeypatch):
    monkeypatch.setattr(
        calendar_tools,
        "generate_reply",
        lambda prompt, cfg=None, context=None: (
            '{"is_calendar_request": true, "action": "lookup", "query": null, '
            '"when_text": null, "new_title": null, "new_location": null, '
            '"new_description": null, "window_days": 2}'
        ),
        raising=True,
    )

    plan = calendar_tools.maybe_plan_calendar_request(
        "Could you give me the rundown on what my schedule looks like tomorrow?",
        conversation_id=204,
    )

    assert plan is not None
    assert plan.is_calendar_request is True
    assert plan.action == "lookup"
    assert plan.window_days == 2


def test_calendar_planner_handles_relative_move_phrase():
    plan = calendar_tools.maybe_plan_calendar_request(
        "Shift project sync back an hour on my calendar",
        conversation_id=205,
    )

    assert plan is not None
    assert plan.is_calendar_request is True
    assert plan.action == "move"
    assert plan.query == "project sync"
    assert plan.when_text == "back an hour"


def test_calendar_planner_uses_context_for_pronoun_location_update():
    calendar_tools._calendar_context["206"] = calendar_tools.CalendarConversationContext(
        last_action="details",
        last_query="Project sync",
    )

    plan = calendar_tools.maybe_plan_calendar_request(
        "Make Zoom the location for that meeting",
        conversation_id=206,
    )

    assert plan is not None
    assert plan.is_calendar_request is True
    assert plan.action == "update_location"
    assert plan.query == "Project sync"
    assert plan.new_location == "Zoom"


def test_calendar_planner_can_use_llm_for_fuzzy_move_with_context(monkeypatch):
    calendar_tools._calendar_context["207"] = calendar_tools.CalendarConversationContext(
        last_action="details",
        last_query="Lunch with Sam",
    )
    monkeypatch.setattr(
        calendar_tools,
        "generate_reply",
        lambda prompt, cfg=None, context=None: (
            '{"is_calendar_request": true, "action": "move", "query": null, '
            '"when_text": "back an hour", "new_title": null, "new_location": null, '
            '"new_description": null, "window_days": null}'
        ),
        raising=True,
    )

    plan = calendar_tools.maybe_plan_calendar_request(
        "Can you push that back an hour?",
        conversation_id=207,
    )

    assert plan is not None
    assert plan.action == "move"
    assert plan.query == "Lunch with Sam"
    assert plan.when_text == "back an hour"

