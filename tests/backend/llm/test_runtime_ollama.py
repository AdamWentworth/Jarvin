from __future__ import annotations

from types import SimpleNamespace

import backend.llm.runtime_ollama as rt


def test_chat_completion_returns_none_when_model_not_configured(monkeypatch):
    fake_settings = SimpleNamespace(
        ollama_base_url="http://127.0.0.1:11434",
        ollama_model="",
        ollama_timeout_sec=30.0,
    )
    monkeypatch.setattr(rt.cfg, "settings", fake_settings, raising=True)

    out = rt.chat_completion(
        system_prompt="system",
        user_text="hello",
        temperature=0.2,
        max_tokens=32,
    )

    assert out is None


def test_chat_completion_posts_to_ollama_api(monkeypatch):
    fake_settings = SimpleNamespace(
        ollama_base_url="http://127.0.0.1:11434/",
        ollama_model="my-model",
        ollama_timeout_sec=15.0,
    )
    monkeypatch.setattr(rt.cfg, "settings", fake_settings, raising=True)

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": "  hello from ollama  "}}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(rt.requests, "post", fake_post, raising=True)

    out = rt.chat_completion(
        system_prompt="be helpful",
        user_text="hi there",
        temperature=0.5,
        max_tokens=64,
    )

    assert out == "hello from ollama"
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["json"]["model"] == "my-model"
    assert captured["json"]["stream"] is False
    assert captured["json"]["messages"][0]["role"] == "system"
    assert captured["json"]["messages"][1]["role"] == "user"
    assert captured["json"]["options"]["temperature"] == 0.5
    assert captured["json"]["options"]["num_predict"] == 64
    assert captured["timeout"] == 15.0


def test_probe_server_lists_models(monkeypatch):
    fake_settings = SimpleNamespace(
        ollama_base_url="http://127.0.0.1:11434/",
        ollama_model="my-model",
        ollama_timeout_sec=20.0,
    )
    monkeypatch.setattr(rt.cfg, "settings", fake_settings, raising=True)

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"models": [{"name": "my-model"}, {"name": "other-model"}]}

    monkeypatch.setattr(rt.requests, "get", lambda url, timeout: FakeResponse(), raising=True)

    info = rt.probe_server()

    assert info["base_url"] == "http://127.0.0.1:11434"
    assert info["model"] == "my-model"
    assert info["models"] == ["my-model", "other-model"]
