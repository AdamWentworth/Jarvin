from __future__ import annotations

from types import SimpleNamespace

import backend.util.hw_detect as hw


def test_detect_hardware_falls_back_to_nvidia_smi_when_torch_missing(monkeypatch):
    monkeypatch.setattr(hw, "torch", None, raising=False)
    monkeypatch.setattr(hw.psutil, "cpu_count", lambda logical=True: 8, raising=True)
    monkeypatch.setattr(
        hw.psutil,
        "virtual_memory",
        lambda: SimpleNamespace(total=16 * 1024 ** 3),
        raising=True,
    )

    def fake_check_output(cmd, stderr=None, text=None, timeout=None):
        query = next(part for part in cmd if part.startswith("--query-gpu="))
        if query == "--query-gpu=name":
            return "NVIDIA GeForce GTX 1070\n"
        if query == "--query-gpu=memory.total":
            return "8192\n"
        raise AssertionError(f"unexpected query: {query}")

    monkeypatch.setattr(hw.subprocess, "check_output", fake_check_output, raising=True)

    profile = hw.detect_hardware()

    assert profile.has_nvidia is True
    assert profile.cuda_name == "NVIDIA GeForce GTX 1070"
    assert profile.vram_gb == 8.0
    assert profile.has_mps is False
