from __future__ import annotations

from types import SimpleNamespace

import backend.llm.runtime_router as rt


def test_router_uses_llama_cpp_backend(monkeypatch):
    fake_settings = SimpleNamespace(llm_backend="llama_cpp")
    monkeypatch.setattr(rt.cfg, "settings", fake_settings, raising=True)
    monkeypatch.setattr(rt, "llama_chat_completion", lambda **kwargs: "from-llama", raising=True)

    out = rt.chat_completion(
        system_prompt="system",
        user_text="hello",
        temperature=0.1,
        max_tokens=16,
    )

    assert out == "from-llama"


def test_router_uses_ollama_backend(monkeypatch):
    fake_settings = SimpleNamespace(llm_backend="ollama_http")
    monkeypatch.setattr(rt.cfg, "settings", fake_settings, raising=True)
    monkeypatch.setattr(
        rt.runtime_ollama,
        "chat_completion",
        lambda **kwargs: "from-ollama",
        raising=True,
    )

    out = rt.chat_completion(
        system_prompt="system",
        user_text="hello",
        temperature=0.1,
        max_tokens=16,
    )

    assert out == "from-ollama"
