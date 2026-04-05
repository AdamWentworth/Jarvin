from __future__ import annotations

import backend.agent.briefing.brief_request_planner as brief_planner


def test_brief_planner_handles_rundown_phrase():
    plan = brief_planner.maybe_plan_brief_request(
        "Give me the rundown for today in Portland",
        conversation_id=501,
    )

    assert plan is not None
    assert plan.is_brief_request is True
    assert plan.day_offset == 0
    assert plan.location_hint == "Portland"


def test_brief_planner_uses_context_for_tomorrow_follow_up():
    brief_planner.remember_brief_context(502, day_offset=0, location_hint="Burnaby")
    try:
        plan = brief_planner.maybe_plan_brief_request("How about tomorrow?", conversation_id=502)

        assert plan is not None
        assert plan.is_brief_request is True
        assert plan.day_offset == 1
        assert plan.location_hint == "Burnaby"
    finally:
        brief_planner.clear_brief_context(502)

