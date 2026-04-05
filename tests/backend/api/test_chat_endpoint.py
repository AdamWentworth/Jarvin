# tests/backend/api/test_chat_endpoint.py
from __future__ import annotations

import pytest

from backend.api.schemas import ChatRequest
import backend.api.routes.chat as chat_mod


@pytest.mark.asyncio
async def test_chat_endpoint_rejects_empty_text():
    payload = ChatRequest(user_text="   ")
    resp = await chat_mod.chat_endpoint(payload)
    assert hasattr(resp, "error")
    assert "empty" in resp.error


@pytest.mark.asyncio
async def test_chat_endpoint_returns_reply_and_persists_turns(monkeypatch):
    calls = {"get_profile": 0, "get_history": 0, "append": [], "mode": None}

    def fake_get_user_profile():
        calls["get_profile"] += 1
        return {"name": "Test", "goal": "Testing"}

    def fake_get_conversation_history(conversation_id=None):
        calls["get_history"] += 1
        return [("user", "hello"), ("assistant", "hi")]

    def fake_append_turn(role, message, conversation_id=None, **kwargs):
        calls["append"].append((role, message, conversation_id, kwargs))

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

    resp = await chat_mod.chat_endpoint(payload)

    assert hasattr(resp, "reply")
    assert resp.reply == "echo: ping"
    assert resp.mode_used == "chat_balanced"
    assert resp.conversation_id is None
    assert calls["get_profile"] == 1
    assert calls["get_history"] == 1
    assert calls["mode"] == "chat_balanced"
    assert len(calls["append"]) == 2
    assert calls["append"][0] == ("user", "ping", None, {})
    assert calls["append"][1] == ("assistant", "echo: ping", None, {})


@pytest.mark.asyncio
async def test_chat_endpoint_can_disable_profile_and_history(monkeypatch):
    monkeypatch.setattr(chat_mod, "get_user_profile", lambda: {"should_not": "be called"}, raising=True)
    monkeypatch.setattr(chat_mod, "get_conversation_history", lambda: [("user", "x")], raising=True)
    monkeypatch.setattr(chat_mod, "append_turn", lambda role, message, conversation_id=None, **kwargs: None, raising=True)
    monkeypatch.setattr(chat_mod, "generate_reply", lambda text, cfg=None, context=None: "ok", raising=True)

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
    monkeypatch.setattr(chat_mod, "append_turn", lambda role, message, conversation_id=None, **kwargs: None, raising=True)

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

    def fake_append_turn(role, message, conversation_id=None, **kwargs):
        calls["append"].append((role, message, conversation_id, kwargs))

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
    assert calls["append"] == [
        ("user", "hello", 42, {}),
        ("assistant", "ok", 42, {}),
    ]


@pytest.mark.asyncio
async def test_chat_endpoint_can_include_tts_url(monkeypatch):
    monkeypatch.setattr(chat_mod, "get_user_profile", lambda: {}, raising=True)
    monkeypatch.setattr(chat_mod, "get_conversation_history", lambda conversation_id=None: [], raising=True)
    monkeypatch.setattr(chat_mod, "append_turn", lambda role, message, conversation_id=None, **kwargs: None, raising=True)
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


@pytest.mark.asyncio
async def test_chat_endpoint_can_handle_tool_commands(monkeypatch):
    calls = {"append": [], "generate_reply": 0}

    monkeypatch.setattr(chat_mod, "get_user_profile", lambda: {}, raising=True)
    monkeypatch.setattr(chat_mod, "get_conversation_history", lambda conversation_id=None: [], raising=True)
    monkeypatch.setattr(
        chat_mod,
        "append_turn",
        lambda role, message, conversation_id=None, **kwargs: calls["append"].append((role, message, conversation_id, kwargs)),
        raising=True,
    )
    monkeypatch.setattr(
        chat_mod,
        "generate_reply",
        lambda text, cfg=None, context=None: calls.__setitem__("generate_reply", calls["generate_reply"] + 1) or "should not happen",
        raising=True,
    )
    monkeypatch.setattr(
        chat_mod,
        "maybe_handle_assistant_tool_request",
        lambda text, conversation_id=None, agent_access_mode=None: type(
            "ToolReply",
            (),
            {"handled": True, "reply": "Search results for `todo`: ...", "tool_kind": None, "tool_payload": None},
        )(),
        raising=True,
    )

    resp = await chat_mod.chat_endpoint(ChatRequest(user_text="/tool search todo"))

    assert resp.reply == "Search results for `todo`: ..."
    assert resp.mode_used == "agent_tool"
    assert calls["generate_reply"] == 0
    assert calls["append"][0] == ("user", "/tool search todo", None, {})
    assert calls["append"][1] == ("assistant", "Search results for `todo`: ...", None, {"tool_kind": None, "tool_payload": None})


@pytest.mark.asyncio
async def test_chat_endpoint_can_speak_tool_command_replies(monkeypatch):
    monkeypatch.setattr(chat_mod, "get_user_profile", lambda: {}, raising=True)
    monkeypatch.setattr(chat_mod, "get_conversation_history", lambda conversation_id=None: [], raising=True)
    monkeypatch.setattr(chat_mod, "append_turn", lambda role, message, conversation_id=None, **kwargs: None, raising=True)
    monkeypatch.setattr(
        chat_mod,
        "maybe_handle_assistant_tool_request",
        lambda text, conversation_id=None, agent_access_mode=None: type(
            "ToolReply",
            (),
            {
                "handled": True,
                "reply": "Weather for Seattle",
                "tool_kind": "weather",
                "tool_payload": {"summary": "Clear sky", "icon_name": "sun"},
            },
        )(),
        raising=True,
    )
    monkeypatch.setattr(chat_mod, "synth_to_wav", lambda text: r"D:\Projects\Jarvin\temp\tts_tool.wav", raising=True)

    resp = await chat_mod.chat_endpoint(ChatRequest(user_text="/tool weather Seattle", speak_reply=True))

    assert resp.reply == "Weather for Seattle"
    assert resp.mode_used == "agent_tool"
    assert resp.tts_url == "/_temp/tts_tool.wav"
    assert resp.tool_kind == "weather"
    assert resp.tool_payload["icon_name"] == "sun"


@pytest.mark.asyncio
async def test_chat_endpoint_passes_conversation_id_to_tool_router(monkeypatch):
    captured = {}

    monkeypatch.setattr(chat_mod, "get_user_profile", lambda: {}, raising=True)
    monkeypatch.setattr(chat_mod, "get_conversation_history", lambda conversation_id=None: [], raising=True)
    monkeypatch.setattr(chat_mod, "append_turn", lambda role, message, conversation_id=None, **kwargs: None, raising=True)

    def fake_tool_router(text, conversation_id=None, agent_access_mode=None):
        captured["text"] = text
        captured["conversation_id"] = conversation_id
        captured["agent_access_mode"] = agent_access_mode
        return type("ToolReply", (), {"handled": True, "reply": "Handled via tool", "tool_kind": None, "tool_payload": None})()

    monkeypatch.setattr(chat_mod, "maybe_handle_assistant_tool_request", fake_tool_router, raising=True)

    resp = await chat_mod.chat_endpoint(
        ChatRequest(
            user_text="delete lunch from my calendar",
            conversation_id=77,
            agent_access_mode="approve_risky",
        )
    )

    assert resp.reply == "Handled via tool"
    assert resp.conversation_id == 77
    assert captured == {
        "text": "delete lunch from my calendar",
        "conversation_id": 77,
        "agent_access_mode": "approve_risky",
    }
