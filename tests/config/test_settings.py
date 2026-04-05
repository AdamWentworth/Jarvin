# tests/config/test_settings.py
from __future__ import annotations

import os
from pathlib import Path

import pytest

from config import Settings


def test_settings_env_overrides_sample_rate_and_log_level(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIN_SAMPLE_RATE", "44100")
    monkeypatch.setenv("JARVIN_LOG_LEVEL", "debug")
    monkeypatch.setenv("JARVIN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("JARVIN_DB_FILENAME", "test.sqlite3")

    s = Settings()

    assert s.sample_rate == 44_100
    assert s.log_level == "debug"
    # defaults unaffected
    assert s.chunk == 1024


@pytest.mark.parametrize(
    "value,expected",
    [
        ("DEBUG", "debug"),
        (" Info ", "info"),
        ("warn", "info"),     # invalid => fallback to info
        ("", "info"),         # empty => fallback
    ],
)
def test_log_level_validator(value, expected, monkeypatch):
    monkeypatch.setenv("JARVIN_LOG_LEVEL", value)
    s = Settings()
    assert s.log_level == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        ("", None),
        ("none", None),
        ("auto", None),
        ("tiny", "tiny"),
        ("BASE", "base"),
        ("unknown", "small"),  # invalid => safe default
    ],
)
def test_whisper_model_size_validator(value, expected, monkeypatch):
    if value is None:
        monkeypatch.delenv("JARVIN_WHISPER_MODEL_SIZE", raising=False)
    else:
        monkeypatch.setenv("JARVIN_WHISPER_MODEL_SIZE", value)

    s = Settings()
    assert s.whisper_model_size == expected


def test_db_path_creates_directory(tmp_path, monkeypatch):
    data_dir = tmp_path / "mydata"
    monkeypatch.setenv("JARVIN_DATA_DIR", str(data_dir))
    monkeypatch.setenv("JARVIN_DB_FILENAME", "jarvin.sqlite3")

    s = Settings()
    path = Path(s.db_path)

    assert path.name == "jarvin.sqlite3"
    assert path.parent == data_dir.resolve()
    # Directory should exist as a side-effect of accessing db_path
    assert path.parent.is_dir()


@pytest.mark.parametrize(
    "value,expected",
    [
        ("llama_cpp", "llama_cpp"),
        ("OLLAMA_HTTP", "ollama_http"),
        ("unknown", "llama_cpp"),
        ("", "llama_cpp"),
    ],
)
def test_llm_backend_validator(value, expected, monkeypatch):
    monkeypatch.setenv("JARVIN_LLM_BACKEND", value)
    s = Settings()
    assert s.llm_backend == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("read_only", "read_only"),
        ("APPROVE_RISKY", "approve_risky"),
        ("full_access", "full_access"),
        ("something_else", "approve_risky"),
    ],
)
def test_agent_default_access_mode_validator(value, expected, monkeypatch):
    monkeypatch.setenv("JARVIN_AGENT_DEFAULT_ACCESS_MODE", value)
    s = Settings()
    assert s.agent_default_access_mode == expected
