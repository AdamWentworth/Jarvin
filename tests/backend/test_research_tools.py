from __future__ import annotations

import backend.agent.research.research_request_tools as research_tools


def test_research_planner_handles_natural_research_phrase():
    plan = research_tools.maybe_plan_research_request(
        "Could you look into local llm benchmark results and summarize what you find?",
        conversation_id=401,
    )

    assert plan is not None
    assert plan.is_research_request is True
    assert plan.action == "web_search"
    assert plan.query == "local llm benchmark results"


def test_research_planner_handles_follow_up_with_context():
    research_tools.remember_research_context(402, action="web_search", query="llama.cpp windows cuda docs")
    try:
        plan = research_tools.maybe_plan_research_request("What else did you find?", conversation_id=402)

        assert plan is not None
        assert plan.action == "web_search"
        assert plan.query == "llama.cpp windows cuda docs"
    finally:
        research_tools.clear_research_context(402)


def test_research_planner_preserves_google_request():
    plan = research_tools.maybe_plan_research_request("Google qwen2.5 3b gguf", conversation_id=403)

    assert plan is not None
    assert plan.is_research_request is True
    assert plan.action == "google_search"
    assert plan.query == "qwen2.5 3b gguf"

