# tests/backend/api/test_chat_endpoint.py
from __future__ import annotations

import pytest

from backend.api.schemas import ChatRequest
import backend.api.routes.chat as chat_mod


@pytest.mark.asyncio
async def test_chat_endpoint_rejects_empty_text():
    payload = ChatRequest(user_text="   ")
    resp = await chat_mod.chat_endpoint(payload)
    # ErrorResponse has `.error` field; ChatResponse has `.reply`
    assert hasattr(resp, "error")
    assert "empty" in resp.error


@pytest.mark.asyncio
async def test_chat_endpoint_returns_reply_and_persists_turns(monkeypatch):
    # --- arrange: mock memory + AI engine ---
    calls = {"get_profile": 0, "get_history": 0, "append": []}

    def fake_get_user_profile():
        calls["get_profile"] += 1
        return {"name": "Test", "goal": "Testing"}

    def fake_get_conversation_history():
        calls["get_history"] += 1
        return [("user", "hello"), ("assistant", "hi")]

    def fake_append_turn(role, message, conversation_id=None):
        calls["append"].append((role, message, conversation_id))

    def fake_generate_reply(text, cfg=None, context=None):
        # simple, deterministic reply so tests are stable
        return f"echo: {text}"

    monkeypatch.setattr(chat_mod, "get_user_profile", fake_get_user_profile, raising=True)
    monkeypatch.setattr(chat_mod, "get_conversation_history", fake_get_conversation_history, raising=True)
    monkeypatch.setattr(chat_mod, "append_turn", fake_append_turn, raising=True)
    monkeypatch.setattr(chat_mod, "generate_reply", fake_generate_reply, raising=True)

    payload = ChatRequest(
        user_text="ping",
        use_profile=True,
        use_history=True,
        history_window=3,
    )

    # --- act ---
    resp = await chat_mod.chat_endpoint(payload)

    # --- assert ---
    assert hasattr(resp, "reply")
    assert resp.reply == "echo: ping"

    # profile + history consulted once
    assert calls["get_profile"] == 1
    assert calls["get_history"] == 1

    # two turns appended: user + assistant
    assert len(calls["append"]) == 2
    assert calls["append"][0][0] == "user"
    assert calls["append"][0][1] == "ping"
    assert calls["append"][1][0] == "assistant"
    assert calls["append"][1][1] == "echo: ping"


@pytest.mark.asyncio
async def test_chat_endpoint_can_disable_profile_and_history(monkeypatch):
    # ensure disabling avoids calling memory helpers
    monkeypatch.setattr(chat_mod, "get_user_profile", lambda: {"should_not": "be called"}, raising=True)
    monkeypatch.setattr(chat_mod, "get_conversation_history", lambda: [("user", "x")], raising=True)

    monkeypatch.setattr(
        chat_mod,
        "append_turn",
        lambda role, message, conversation_id=None: None,
        raising=True,
    )
    monkeypatch.setattr(
        chat_mod,
        "generate_reply",
        lambda text, cfg=None, context=None: "ok",
        raising=True,
    )

    payload = ChatRequest(
        user_text="hello",
        use_profile=False,
        use_history=False,
    )
    resp = await chat_mod.chat_endpoint(payload)

    assert hasattr(resp, "reply")
    assert resp.reply == "ok"
