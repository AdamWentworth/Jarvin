from __future__ import annotations

import pytest
from fastapi import HTTPException

import backend.api.routes.workspace as workspace_mod
from backend.api.schemas import ConversationCreateRequest, ConversationRenameRequest, UserProfilePayload


def _install_fake_workspace(monkeypatch):
    state = {
        "profile": {
            "name": "Captain Monk",
            "goal": "Build Jarvin",
            "mood": "Focused",
            "communication_style": "Friendly",
            "response_length": "Balanced",
        },
        "active": 2,
        "conversations": [
            {"id": 2, "title": "Current chat", "created_at": "2026-04-03T13:00:00Z"},
            {"id": 1, "title": "Older chat", "created_at": "2026-04-03T12:00:00Z"},
        ],
        "history": {
            2: [
                {"role": "user", "message": "hello", "tool_kind": None, "tool_payload": None},
                {
                    "role": "assistant",
                    "message": "hi there",
                    "tool_kind": "weather",
                    "tool_payload": {"summary": "Partly cloudy", "icon_name": "cloud-sun"},
                },
            ],
            1: [
                {"role": "user", "message": "old", "tool_kind": None, "tool_payload": None},
                {"role": "assistant", "message": "older", "tool_kind": None, "tool_payload": None},
            ],
        },
        "next_id": 3,
    }

    def get_user_profile():
        return dict(state["profile"])

    def set_user_profile(profile):
        state["profile"] = dict(profile)

    def list_conversations():
        items = []
        for item in state["conversations"]:
            items.append(
                {
                    **item,
                    "messages": len(state["history"].get(int(item["id"]), [])),
                }
            )
        return items

    def get_active_conversation_id():
        return int(state["active"])

    def get_conversation_turns(conversation_id=None):
        cid = int(conversation_id if conversation_id is not None else state["active"])
        return list(state["history"].get(cid, []))

    def new_conversation(title=None, activate=True):
        cid = state["next_id"]
        state["next_id"] += 1
        final_title = (title or "").strip() or f"New conversation {cid}"
        state["conversations"].insert(0, {"id": cid, "title": final_title, "created_at": None})
        state["history"][cid] = []
        if activate:
            state["active"] = cid
        return cid

    def set_active_conversation(conversation_id):
        ids = {int(item["id"]) for item in state["conversations"]}
        if int(conversation_id) not in ids:
            raise ValueError(f"Conversation {conversation_id} does not exist.")
        state["active"] = int(conversation_id)

    def rename_conversation(conversation_id, title):
        for item in state["conversations"]:
            if int(item["id"]) == int(conversation_id):
                item["title"] = title
                return

    def clear_conversation(conversation_id=None):
        cid = int(conversation_id if conversation_id is not None else state["active"])
        state["history"][cid] = []

    def delete_conversation(conversation_id):
        cid = int(conversation_id)
        state["conversations"] = [item for item in state["conversations"] if int(item["id"]) != cid]
        state["history"].pop(cid, None)
        if state["active"] == cid and state["conversations"]:
            state["active"] = int(state["conversations"][0]["id"])

    monkeypatch.setattr(workspace_mod, "get_user_profile", get_user_profile, raising=True)
    monkeypatch.setattr(workspace_mod, "set_user_profile", set_user_profile, raising=True)
    monkeypatch.setattr(workspace_mod, "list_conversations", list_conversations, raising=True)
    monkeypatch.setattr(workspace_mod, "get_active_conversation_id", get_active_conversation_id, raising=True)
    monkeypatch.setattr(workspace_mod, "get_conversation_turns", get_conversation_turns, raising=True)
    monkeypatch.setattr(workspace_mod, "new_conversation", new_conversation, raising=True)
    monkeypatch.setattr(workspace_mod, "set_active_conversation", set_active_conversation, raising=True)
    monkeypatch.setattr(workspace_mod, "rename_conversation", rename_conversation, raising=True)
    monkeypatch.setattr(workspace_mod, "clear_conversation", clear_conversation, raising=True)
    monkeypatch.setattr(workspace_mod, "delete_conversation", delete_conversation, raising=True)
    return state


@pytest.mark.asyncio
async def test_workspace_bootstrap_returns_profile_and_active_history(monkeypatch):
    _install_fake_workspace(monkeypatch)

    resp = await workspace_mod.workspace_bootstrap()

    assert resp.profile.name == "Captain Monk"
    assert resp.active_conversation_id == 2
    assert len(resp.conversations) == 2
    assert resp.conversations[0].is_active is True
    assert resp.history[0].message == "hello"
    assert resp.history[1].tool_kind == "weather"
    assert resp.history[1].tool_payload["icon_name"] == "cloud-sun"


@pytest.mark.asyncio
async def test_profile_put_round_trips_saved_values(monkeypatch):
    _install_fake_workspace(monkeypatch)

    resp = await workspace_mod.put_profile(
        UserProfilePayload(
            name="Jarvin User",
            goal="Ship desktop app",
            mood="Curious",
            communication_style="Direct",
            response_length="Detailed",
        )
    )

    assert resp.name == "Jarvin User"
    assert resp.goal == "Ship desktop app"
    assert resp.response_length == "Detailed"


@pytest.mark.asyncio
async def test_conversation_mutations_return_updated_workspace(monkeypatch):
    state = _install_fake_workspace(monkeypatch)

    created = await workspace_mod.create_conversation(ConversationCreateRequest(title="Fresh chat"))
    assert created.active_conversation_id == 3
    assert created.conversations[0].title == "Fresh chat"

    renamed = await workspace_mod.rename_conversation_route(3, ConversationRenameRequest(title="Renamed chat"))
    assert renamed.conversations[0].title == "Renamed chat"

    activated = await workspace_mod.activate_conversation(1)
    assert activated.active_conversation_id == 1
    assert activated.history[0].message == "old"

    cleared = await workspace_mod.clear_conversation_route(1)
    assert cleared.history == []

    deleted = await workspace_mod.delete_conversation_route(1)
    assert deleted.active_conversation_id == state["active"]
    assert all(item.id != 1 for item in deleted.conversations)


@pytest.mark.asyncio
async def test_delete_conversation_blocks_only_remaining_chat(monkeypatch):
    state = _install_fake_workspace(monkeypatch)
    state["conversations"] = [{"id": 2, "title": "Only chat", "created_at": None}]
    state["history"] = {
        2: [{"role": "user", "message": "hello", "tool_kind": None, "tool_payload": None}],
    }
    state["active"] = 2

    with pytest.raises(HTTPException) as exc:
        await workspace_mod.delete_conversation_route(2)

    assert exc.value.status_code == 400
