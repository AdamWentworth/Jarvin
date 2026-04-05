from __future__ import annotations

import pytest
from fastapi import HTTPException

import backend.api.routes.agent_approvals as agent_approvals_mod
from backend.api.schemas import ApprovalDecisionRequest


@pytest.mark.asyncio
async def test_agent_approval_route_returns_chat_response(monkeypatch):
    captured = {"append": []}

    monkeypatch.setattr(
        agent_approvals_mod,
        "maybe_handle_assistant_tool_request",
        lambda text, conversation_id=None, client_session_id=None: type(
            "ToolReply",
            (),
            {
                "handled": True,
                "reply": "Command `git status` exited with `0`.",
                "tool_kind": None,
                "tool_payload": None,
            },
        )(),
        raising=True,
    )
    monkeypatch.setattr(
        agent_approvals_mod,
        "append_turn",
        lambda role, message, conversation_id=None, **kwargs: captured["append"].append(
            (role, message, conversation_id, kwargs)
        ),
        raising=True,
    )

    response = await agent_approvals_mod.respond_to_agent_approval(
        ApprovalDecisionRequest(decision="approve", conversation_id=12)
    )

    assert response.reply == "Command `git status` exited with `0`."
    assert response.mode_used == "agent_approval"
    assert response.conversation_id == 12
    assert captured["append"] == [
        ("assistant", "Command `git status` exited with `0`.", 12, {"tool_kind": None, "tool_payload": None})
    ]


@pytest.mark.asyncio
async def test_agent_approval_route_rejects_empty_decision():
    with pytest.raises(HTTPException) as exc:
        await agent_approvals_mod.respond_to_agent_approval(
            ApprovalDecisionRequest(decision="   ", conversation_id=4)
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "empty approval decision"


@pytest.mark.asyncio
async def test_agent_approval_route_raises_conflict_when_nothing_is_pending(monkeypatch):
    monkeypatch.setattr(
        agent_approvals_mod,
        "maybe_handle_assistant_tool_request",
        lambda text, conversation_id=None, client_session_id=None: type(
            "ToolReply",
            (),
            {"handled": False, "reply": "", "tool_kind": None, "tool_payload": None},
        )(),
        raising=True,
    )

    with pytest.raises(HTTPException) as exc:
        await agent_approvals_mod.respond_to_agent_approval(
            ApprovalDecisionRequest(decision="approve", conversation_id=21)
        )

    assert exc.value.status_code == 409
    assert "No pending approval matched" in exc.value.detail
