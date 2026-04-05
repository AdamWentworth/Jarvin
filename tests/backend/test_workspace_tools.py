from __future__ import annotations

import backend.agent.workspace_tools as workspace_tools


def test_workspace_planner_handles_fuzzy_repo_search():
    plan = workspace_tools.maybe_plan_workspace_request(
        "Could you look through the codebase for include_router?",
        conversation_id=301,
    )

    assert plan is not None
    assert plan.is_workspace_request is True
    assert plan.action == "search_repo"
    assert plan.query == "include_router"


def test_workspace_planner_handles_file_read_with_line_range():
    plan = workspace_tools.maybe_plan_workspace_request(
        "Pull up backend/api/app.py lines 10 to 30",
        conversation_id=302,
    )

    assert plan is not None
    assert plan.is_workspace_request is True
    assert plan.action == "read_file"
    assert plan.path == "backend/api/app.py"
    assert plan.start_line == 10
    assert plan.end_line == 30


def test_workspace_planner_handles_common_git_question():
    plan = workspace_tools.maybe_plan_workspace_request(
        "What changed recently in the repo?",
        conversation_id=303,
    )

    assert plan is not None
    assert plan.is_workspace_request is True
    assert plan.action == "run_command"
    assert plan.command == "git diff --stat"


def test_workspace_planner_uses_context_for_show_more():
    workspace_tools.remember_workspace_context(
        304,
        action="read_file",
        path="backend/api/app.py",
        start_line=1,
        end_line=40,
    )
    try:
        plan = workspace_tools.maybe_plan_workspace_request("show me more", conversation_id=304)

        assert plan is not None
        assert plan.action == "read_file"
        assert plan.path == "backend/api/app.py"
        assert plan.start_line == 41
    finally:
        workspace_tools.clear_workspace_context(304)
