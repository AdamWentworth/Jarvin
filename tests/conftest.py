# tests/conftest.py
from __future__ import annotations

import os
import sys
import tempfile
from unittest import mock

import pytest

# --- FORCE PROJECT ROOT ONTO sys.path ----------------------------------------

# Project root = parent of the "tests" directory
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ensure project root is at the *front* of sys.path so it wins over site-packages
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# -----------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _test_env_isolation():
    """
    Session-wide defaults so tests don't:
      - download GGUF models
      - open browsers
      - write DBs under ./data
    """
    tmp_root = tempfile.mkdtemp(prefix="jarvin_test_")

    os.environ.setdefault("JARVIN_DATA_DIR", os.path.join(tmp_root, "data"))
    os.environ.setdefault("JARVIN_DB_FILENAME", "jarvin_test.sqlite3")
    os.environ.setdefault("JARVIN_DB_WAL", "false")
    os.environ.setdefault("JARVIN_LLM_AUTO_PROVISION", "false")
    os.environ.setdefault("JARVIN_GRADIO_AUTO_OPEN", "false")
    os.environ.setdefault("JARVIN_TEMP_DIR", os.path.join(tmp_root, "temp"))

    # let tests run; per-test fixtures can tighten further
    yield


@pytest.fixture(autouse=True)
def _stub_external_llm_and_hf(monkeypatch):
    """
    Per-test: prevent any real llama.cpp or HF network IO.

    - huggingface_hub.snapshot_download => RuntimeError if accidentally used
    - backend.llm.runtime_llama_cpp._load_llama => None by default
    """
    # If huggingface_hub is importable, stub snapshot_download so an accidental
    # call fails fast and loudly.
    try:
        import huggingface_hub  # type: ignore

        monkeypatch.setattr(
            huggingface_hub,
            "snapshot_download",
            lambda *a, **k: (_ for _ in ()).throw(
                RuntimeError("snapshot_download used in tests; must be mocked")
            ),
            raising=True,
        )
    except Exception:
        # huggingface_hub not installed – nothing to do
        pass

    # runtime_llama_cpp: ensure _load_llama() returns None unless tests override it
    try:
        from backend.llm import runtime_llama_cpp as rt

        if hasattr(rt, "_load_llama"):
            # If _load_llama used to be an lru_cache this clears it; if not, and this
            # ever raises, the except below will swallow it and tests that care can
            # patch explicitly.
            try:
                rt._load_llama.cache_clear()  # type: ignore[attr-defined]
            except AttributeError:
                pass

            monkeypatch.setattr(rt, "_load_llama", lambda: None, raising=True)
    except Exception:
        # If import fails, tests that care will import/patch explicitly
        pass
