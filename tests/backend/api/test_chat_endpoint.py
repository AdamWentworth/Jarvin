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
    calls = {"get_profile": 0, "get_history": 0, "append": [], "mode": None}

    def fake_get_user_profile():
        calls["get_profile"] += 1
        return {"name": "Test", "goal": "Testing"}

    def fake_get_conversation_history(conversation_id=None):
        calls["get_history"] += 1
        return [("user", "hello"), ("assistant", "hi")]

    def fake_append_turn(role, message, conversation_id=None):
        calls["append"].append((role, message, conversation_id))

    def fake_generate_reply(text, cfg=None, context=None):
        calls["mode"] = getattr(cfg, "mode", None)
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
    assert resp.mode_used == "chat_balanced"
    assert resp.conversation_id is None

    # profile + history consulted once
    assert calls["get_profile"] == 1
    assert calls["get_history"] == 1
    assert calls["mode"] == "chat_balanced"

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
    assert resp.mode_used == "chat_balanced"
    assert resp.conversation_id is None


@pytest.mark.asyncio
async def test_chat_endpoint_uses_requested_mode(monkeypatch):
    captured = {}

    monkeypatch.setattr(chat_mod, "get_user_profile", lambda: {}, raising=True)
    monkeypatch.setattr(chat_mod, "get_conversation_history", lambda: [], raising=True)
    monkeypatch.setattr(
        chat_mod,
        "append_turn",
        lambda role, message, conversation_id=None: None,
        raising=True,
    )

    def fake_generate_reply(text, cfg=None, context=None):
        captured["mode"] = getattr(cfg, "mode", None)
        captured["max_tokens"] = getattr(cfg, "max_tokens", None)
        return "structured reply"

    monkeypatch.setattr(chat_mod, "generate_reply", fake_generate_reply, raising=True)

    payload = ChatRequest(
        user_text="plan the next steps",
        mode="agent_strong",
        use_profile=False,
        use_history=False,
    )
    resp = await chat_mod.chat_endpoint(payload)

    assert resp.reply == "structured reply"
    assert resp.mode_used == "agent_strong"
    assert resp.conversation_id is None
    assert captured["mode"] == "agent_strong"
    assert captured["max_tokens"] == 512


@pytest.mark.asyncio
async def test_chat_endpoint_can_target_specific_conversation(monkeypatch):
    calls = {"history": [], "append": []}

    monkeypatch.setattr(chat_mod, "get_user_profile", lambda: {}, raising=True)

    def fake_get_conversation_history(conversation_id=None):
        calls["history"].append(conversation_id)
        return []

    def fake_append_turn(role, message, conversation_id=None):
        calls["append"].append((role, message, conversation_id))

    monkeypatch.setattr(chat_mod, "get_conversation_history", fake_get_conversation_history, raising=True)
    monkeypatch.setattr(chat_mod, "append_turn", fake_append_turn, raising=True)
    monkeypatch.setattr(chat_mod, "generate_reply", lambda text, cfg=None, context=None: "ok", raising=True)

    payload = ChatRequest(
        user_text="hello",
        conversation_id=42,
        use_profile=False,
        use_history=True,
    )
    resp = await chat_mod.chat_endpoint(payload)

    assert resp.reply == "ok"
    assert resp.conversation_id == 42
    assert calls["history"] == [42]
    assert calls["append"] == [("user", "hello", 42), ("assistant", "ok", 42)]


@pytest.mark.asyncio
async def test_chat_endpoint_can_include_tts_url(monkeypatch):
    monkeypatch.setattr(chat_mod, "get_user_profile", lambda: {}, raising=True)
    monkeypatch.setattr(chat_mod, "get_conversation_history", lambda conversation_id=None: [], raising=True)
    monkeypatch.setattr(
        chat_mod,
        "append_turn",
        lambda role, message, conversation_id=None: None,
        raising=True,
    )
    monkeypatch.setattr(chat_mod, "generate_reply", lambda text, cfg=None, context=None: "spoken reply", raising=True)
    monkeypatch.setattr(chat_mod, "synth_to_wav", lambda text: r"D:\Projects\Jarvin\temp\tts_test.wav", raising=True)

    payload = ChatRequest(
        user_text="hello",
        use_profile=False,
        use_history=False,
        speak_reply=True,
    )
    resp = await chat_mod.chat_endpoint(payload)

    assert resp.reply == "spoken reply"
    assert resp.tts_url == "/_temp/tts_test.wav"
