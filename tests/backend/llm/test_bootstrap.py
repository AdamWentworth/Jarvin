from __future__ import annotations

from types import SimpleNamespace

import pytest

import backend.llm.bootstrap as bt


@pytest.mark.asyncio
async def test_provision_llm_uses_ollama_probe_without_downloading(monkeypatch):
    fake_settings = SimpleNamespace(
        llm_auto_provision=True,
        llm_backend="ollama_http",
    )
    monkeypatch.setattr(bt.cfg, "settings", fake_settings, raising=True)
    monkeypatch.setattr(
        bt.runtime_ollama,
        "probe_server",
        lambda: {
            "base_url": "http://127.0.0.1:11434",
            "model": "my-model",
            "models": ["my-model"],
        },
        raising=True,
    )
    monkeypatch.setattr(
        bt,
        "detect_hardware",
        lambda: (_ for _ in ()).throw(AssertionError("detect_hardware should not run for ollama backend")),
        raising=True,
    )

    out = await bt.provision_llm()

    assert out == "my-model"
