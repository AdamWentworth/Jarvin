from __future__ import annotations

import backend.agent.chat.assistant_chat_tools as chat_tools
from backend.agent.tasks.host_task_planner import PlannedHostTask
from backend.agent.tasks.host_task_state import (
    PendingHostTask,
    clear_pending_host_task,
    clear_running_host_task,
    set_running_host_task,
)
from backend.agent.workspace.workspace_request_tools import WorkspacePlan


def test_multi_step_workspace_request_returns_task_request(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "maybe_plan_host_task_request",
        lambda text, conversation_id=None: PlannedHostTask(
            is_task_request=True,
            title="Inspect startup wiring",
            summary="Read the app router and check repo status.",
            steps=(
                WorkspacePlan(is_workspace_request=True, action="read_file", path="backend/api/app.py"),
                WorkspacePlan(is_workspace_request=True, action="run_command", command="git status"),
            ),
        ),
        raising=True,
    )

    try:
        response = chat_tools.maybe_handle_assistant_tool_request(
            "inspect how startup works and check repo status",
            conversation_id=81,
            agent_access_mode="approve_risky",
        )
    finally:
        clear_pending_host_task(81)

    assert response.handled is True
    assert response.tool_kind == "task_request"
    assert response.tool_payload["status"] == "pending"
    assert len(response.tool_payload["steps"]) == 2


def test_pending_host_task_can_be_approved(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "maybe_plan_host_task_request",
        lambda text, conversation_id=None: PlannedHostTask(
            is_task_request=True,
            title="Check repo health",
            summary="Search the repo and run git status.",
            steps=(
                WorkspacePlan(is_workspace_request=True, action="search_repo", query="include_router"),
                WorkspacePlan(is_workspace_request=True, action="run_command", command="git status"),
            ),
        ),
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "start_host_task_execution",
        lambda pending, **kwargs: chat_tools.ToolChatResponse(
            handled=True,
            reply=f"Started `{pending.title}`.",
            tool_kind="task_request",
            tool_payload={"status": "running", "title": pending.title},
            active_domain="workspace",
            persist_assistant_turn=False,
        ),
        raising=True,
    )

    try:
        pending = chat_tools.maybe_handle_assistant_tool_request(
            "check repo health for me",
            conversation_id=82,
            agent_access_mode="approve_risky",
        )
        approved = chat_tools.maybe_handle_assistant_tool_request(
            "approve",
            conversation_id=82,
        )
    finally:
        clear_pending_host_task(82)

    assert pending.tool_kind == "task_request"
    assert approved.handled is True
    assert approved.tool_kind == "task_request"
    assert approved.persist_assistant_turn is False
    assert "Started `Check repo health`." == approved.reply


def test_host_task_is_blocked_in_read_only_when_command_step_present(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "maybe_plan_host_task_request",
        lambda text, conversation_id=None: PlannedHostTask(
            is_task_request=True,
            title="Inspect repo",
            summary="Read a file and run a git command.",
            steps=(
                WorkspacePlan(is_workspace_request=True, action="read_file", path="backend/api/app.py"),
                WorkspacePlan(is_workspace_request=True, action="run_command", command="git status"),
            ),
        ),
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request(
        "inspect repo",
        conversation_id=83,
        agent_access_mode="read_only",
    )

    assert response.handled is True
    assert response.tool_kind == "task_request"
    assert response.tool_payload["status"] == "blocked"
    assert response.tool_payload["can_approve"] is False


def test_host_task_is_blocked_in_read_only_when_write_step_present(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "maybe_plan_host_task_request",
        lambda text, conversation_id=None: PlannedHostTask(
            is_task_request=True,
            title="Write investigation notes",
            summary="Inspect a file and write notes.",
            steps=(
                WorkspacePlan(is_workspace_request=True, action="read_file", path="backend/api/app.py"),
                WorkspacePlan(is_workspace_request=True, action="write_file", path="notes/findings.txt", content="hello"),
            ),
        ),
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request(
        "inspect the app and write notes",
        conversation_id=86,
        agent_access_mode="read_only",
    )

    assert response.handled is True
    assert response.tool_kind == "task_request"
    assert response.tool_payload["status"] == "blocked"
    assert response.tool_payload["risk_level"] == "high"


def test_low_risk_host_task_can_run_from_read_only(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "maybe_plan_host_task_request",
        lambda text, conversation_id=None: PlannedHostTask(
            is_task_request=True,
            title="Read startup files",
            summary="Read two files on the host.",
            steps=(
                WorkspacePlan(is_workspace_request=True, action="read_file", path="backend/api/app.py"),
                WorkspacePlan(is_workspace_request=True, action="list_directory", path="backend/api"),
            ),
        ),
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "start_host_task_execution",
        lambda pending, **kwargs: chat_tools.ToolChatResponse(
            handled=True,
            reply=f"Started `{pending.title}`.",
            tool_kind="task_request",
            tool_payload={"status": "running", "title": pending.title},
            active_domain="workspace",
            persist_assistant_turn=False,
        ),
        raising=True,
    )

    try:
        pending = chat_tools.maybe_handle_assistant_tool_request(
            "read the startup files",
            conversation_id=84,
            agent_access_mode="read_only",
        )
        approved = chat_tools.maybe_handle_assistant_tool_request(
            "approve",
            conversation_id=84,
        )
    finally:
        clear_pending_host_task(84)

    assert pending.tool_kind == "task_request"
    assert pending.tool_payload["can_approve"] is True
    assert approved.handled is True
    assert approved.reply == "Started `Read startup files`."


def test_task_request_includes_write_preview(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "maybe_plan_host_task_request",
        lambda text, conversation_id=None: PlannedHostTask(
            is_task_request=True,
            title="Write findings",
            summary="Create a notes file on the host.",
            steps=(
                WorkspacePlan(
                    is_workspace_request=True,
                    action="write_file",
                    path="notes/findings.txt",
                    content="Important findings go here.",
                ),
            ),
        ),
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request(
        "write findings to notes/findings.txt",
        conversation_id=87,
        agent_access_mode="approve_risky",
    )

    assert response.handled is True
    assert response.tool_kind == "task_request"
    step = response.tool_payload["steps"][0]
    assert step["action_kind"] == "write_file"
    assert "notes/findings.txt" in (step.get("preview_block") or "")


def test_new_task_is_blocked_while_another_task_is_running(monkeypatch):
    conversation_id = 88
    set_running_host_task(
        conversation_id,
        PendingHostTask(
            title="Existing task",
            summary="Already running",
            risk_level="low",
            steps=(),
        ),
    )
    monkeypatch.setattr(
        chat_tools,
        "maybe_plan_host_task_request",
        lambda text, conversation_id=None: PlannedHostTask(
            is_task_request=True,
            title="Second task",
            summary="Should not start yet.",
            steps=(WorkspacePlan(is_workspace_request=True, action="read_file", path="backend/api/app.py"),),
        ),
        raising=True,
    )

    try:
        response = chat_tools.maybe_handle_assistant_tool_request(
            "inspect something else too",
            conversation_id=conversation_id,
            agent_access_mode="approve_risky",
        )
    finally:
        clear_running_host_task(conversation_id)

    assert response.handled is True
    assert response.tool_kind is None
    assert "already have `Existing task` running" in response.reply
