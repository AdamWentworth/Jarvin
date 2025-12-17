# tests/backend/llm/test_runtime_llama_cpp.py
from __future__ import annotations

from types import SimpleNamespace

import pytest

import backend.llm.runtime_llama_cpp as rt


@pytest.fixture(autouse=True)
def clear_llama_cache():
    """
    Make sure each test sees a clean _load_llama() cache *when* _load_llama
    is an lru_cache-wrapped function. If test or fixtures have monkeypatched
    it to a plain callable (no .cache_clear), skip safely.
    """
    fn = getattr(rt, "_load_llama", None)
    cache_clear = getattr(fn, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()

    yield

    fn = getattr(rt, "_load_llama", None)
    cache_clear = getattr(fn, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()


def test_chat_completion_returns_none_when_llama_unavailable(monkeypatch):
    monkeypatch.setattr(rt, "_load_llama", lambda: None, raising=True)

    out = rt.chat_completion(
        system_prompt="you are a test",
        user_text="hello",
        temperature=0.1,
        max_tokens=16,
    )
    assert out is None


def test_chat_completion_uses_llama_completion(monkeypatch):
    captured = {}

    class FakeLlama:
        def create_chat_completion(self, messages, temperature, max_tokens, stop=None):
            captured["messages"] = messages
            captured["temperature"] = temperature
            captured["max_tokens"] = max_tokens
            # mimic llama-cpp-python response shape
            return {
                "choices": [
                    {"message": {"content": "  hi there  "}},
                ]
            }

    monkeypatch.setattr(rt, "_load_llama", lambda: FakeLlama(), raising=True)

    out = rt.chat_completion(
        system_prompt="you are a test",
        user_text="hello world",
        temperature=0.5,
        max_tokens=32,
    )

    assert out == "hi there"
    assert captured["messages"][0]["role"] == "system"
    assert "you are a test" in captured["messages"][0]["content"]
    assert captured["messages"][1]["role"] == "user"
    assert "hello world" in captured["messages"][1]["content"]
    assert captured["temperature"] == 0.5
    assert captured["max_tokens"] == 32
