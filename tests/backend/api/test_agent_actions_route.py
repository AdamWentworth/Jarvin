from __future__ import annotations

import pytest
from fastapi import HTTPException

import backend.api.routes.agent_actions as agent_actions_mod


@pytest.mark.asyncio
async def test_agent_action_log_route_returns_entries(monkeypatch):
    monkeypatch.setattr(
        agent_actions_mod,
        "list_agent_action_events",
        lambda limit=50, conversation_id=None: [
            {
                "id": 1,
                "created_at": "2026-04-05T10:00:00Z",
                "conversation_id": conversation_id,
                "event_kind": "requested",
                "action_kind": "run_command",
                "risk_level": "medium",
                "access_mode": "approve_risky",
                "title": "Run host command",
                "summary": "Run `git status` on the Jarvin host.",
                "command": "git status",
                "path": None,
                "content_preview": None,
                "detail": "Waiting for approval.",
                "client_session_id": "session-abc",
                "trust_scope": "session",
                "working_directory": r"D:\Projects\Jarvin",
                "argv": ["git", "status"],
                "diff_preview": None,
            }
        ],
        raising=True,
    )

    response = await agent_actions_mod.agent_action_log(limit=10, conversation_id=77)

    assert len(response.actions) == 1
    assert response.actions[0].conversation_id == 77
    assert response.actions[0].command == "git status"
    assert response.actions[0].client_session_id == "session-abc"
    assert response.actions[0].trust_scope == "session"
    assert response.actions[0].working_directory == r"D:\Projects\Jarvin"
    assert response.actions[0].argv == ["git", "status"]


@pytest.mark.asyncio
async def test_agent_action_log_route_raises_http_exception_on_failure(monkeypatch):
    monkeypatch.setattr(
        agent_actions_mod,
        "list_agent_action_events",
        lambda limit=50, conversation_id=None: (_ for _ in ()).throw(RuntimeError("boom")),
        raising=True,
    )

    with pytest.raises(HTTPException) as exc:
        await agent_actions_mod.agent_action_log()

    assert exc.value.status_code == 500
    assert exc.value.detail == "boom"
