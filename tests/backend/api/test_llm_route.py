from __future__ import annotations

from types import SimpleNamespace

import pytest

import backend.api.routes.llm as llm_mod


class _FakeSpec:
    def __init__(self, logical_name: str, quant: str, mem_req_gb: float) -> None:
        self.logical_name = logical_name
        self.quant = quant
        self.mem_req_gb = mem_req_gb


@pytest.mark.asyncio
async def test_get_llm_options_returns_current_local_state(monkeypatch):
    fake_settings = SimpleNamespace(
        llm_backend="llama_cpp",
        llm_force_logical_name="qwen2.5-3b-instruct",
        ollama_model="",
    )
    monkeypatch.setattr(llm_mod.cfg, "settings", fake_settings, raising=True)
    monkeypatch.setattr(
        llm_mod,
        "list_available_specs",
        lambda profile=None: [
            _FakeSpec("qwen2.5-3b-instruct", "Q5_K_M", 4.5),
            _FakeSpec("mistral-7b-instruct", "Q4_K_M", 6.0),
        ],
        raising=True,
    )
    monkeypatch.setattr(llm_mod, "list_ollama_models", lambda: ["phi4:latest"], raising=True)

    resp = await llm_mod.get_llm_options()

    assert resp.current_backend == "llama_cpp"
    assert resp.current_model == "qwen2.5-3b-instruct"
    assert resp.ollama_available is True
    assert [choice.value for choice in resp.local_model_choices] == [
        "qwen2.5-3b-instruct",
        "mistral-7b-instruct",
    ]


@pytest.mark.asyncio
async def test_select_llm_updates_embedded_model(monkeypatch):
    fake_settings = SimpleNamespace(
        llm_backend="llama_cpp",
        llm_force_logical_name="phi-3-mini-4k-instruct",
        ollama_model="",
    )
    monkeypatch.setattr(llm_mod.cfg, "settings", fake_settings, raising=True)
    monkeypatch.setattr(
        llm_mod,
        "list_available_specs",
        lambda profile=None: [_FakeSpec("qwen2.5-3b-instruct", "Q5_K_M", 4.5)],
        raising=True,
    )
    monkeypatch.setattr(llm_mod, "list_ollama_models", lambda: [], raising=True)

    calls = {"reset": 0, "load": 0, "checked": None}

    monkeypatch.setattr(
        llm_mod,
        "get_spec_by_logical_name",
        lambda name: calls.__setitem__("checked", name) or _FakeSpec(name, "Q5_K_M", 4.5),
        raising=True,
    )
    monkeypatch.setattr(
        llm_mod,
        "reset_llama_runtime",
        lambda: calls.__setitem__("reset", calls["reset"] + 1),
        raising=True,
    )
    monkeypatch.setattr(
        llm_mod,
        "ensure_llama_loaded",
        lambda: calls.__setitem__("load", calls["load"] + 1) or object(),
        raising=True,
    )

    resp = await llm_mod.select_llm(
        llm_mod.LLMSelectRequest(backend="llama_cpp", model="qwen2.5-3b-instruct", load_now=True)
    )

    assert fake_settings.llm_backend == "llama_cpp"
    assert fake_settings.llm_force_logical_name == "qwen2.5-3b-instruct"
    assert calls["checked"] == "qwen2.5-3b-instruct"
    assert calls["reset"] == 1
    assert calls["load"] == 1
    assert resp.current_model == "qwen2.5-3b-instruct"


@pytest.mark.asyncio
async def test_select_llm_updates_ollama_backend(monkeypatch):
    fake_settings = SimpleNamespace(
        llm_backend="llama_cpp",
        llm_force_logical_name="phi-3-mini-4k-instruct",
        ollama_model="old-model",
    )
    monkeypatch.setattr(llm_mod.cfg, "settings", fake_settings, raising=True)
    monkeypatch.setattr(
        llm_mod,
        "list_available_specs",
        lambda profile=None: [_FakeSpec("phi-3-mini-4k-instruct", "Q4", 4.0)],
        raising=True,
    )
    monkeypatch.setattr(llm_mod, "list_ollama_models", lambda: ["qwen2.5:latest"], raising=True)

    calls = {"reset": 0}
    monkeypatch.setattr(
        llm_mod,
        "reset_llama_runtime",
        lambda: calls.__setitem__("reset", calls["reset"] + 1),
        raising=True,
    )

    resp = await llm_mod.select_llm(
        llm_mod.LLMSelectRequest(backend="ollama_http", model="qwen2.5:latest", load_now=False)
    )

    assert fake_settings.llm_backend == "ollama_http"
    assert fake_settings.ollama_model == "qwen2.5:latest"
    assert calls["reset"] == 1
    assert resp.current_backend == "ollama_http"
    assert resp.current_model == "qwen2.5:latest"
