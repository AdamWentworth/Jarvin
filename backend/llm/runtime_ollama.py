from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

import config as cfg

log = logging.getLogger("jarvin.ollama")


def _base_url() -> str:
    return str(cfg.settings.ollama_base_url).rstrip("/")


def _timeout() -> float:
    try:
        return max(1.0, float(cfg.settings.ollama_timeout_sec))
    except Exception:
        return 60.0


def _model_name() -> str:
    return str(cfg.settings.ollama_model or "").strip()


def list_models() -> List[str]:
    resp = requests.get(f"{_base_url()}/api/tags", timeout=_timeout())
    resp.raise_for_status()
    data = resp.json() or {}
    models = data.get("models") or []
    out: List[str] = []
    for model in models:
        name = str(model.get("name") or "").strip()
        if name:
            out.append(name)
    return out


def probe_server() -> Dict[str, Any]:
    models = list_models()
    return {
        "base_url": _base_url(),
        "model": _model_name(),
        "models": models,
    }


def chat_completion(
    system_prompt: str,
    user_text: str,
    temperature: float = 0.7,
    max_tokens: int = 256,
) -> Optional[str]:
    model = _model_name()
    if not model:
        log.warning("Ollama backend selected but JARVIN_OLLAMA_MODEL is empty.")
        return None

    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_text.strip()},
        ],
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }

    try:
        resp = requests.post(
            f"{_base_url()}/api/chat",
            json=payload,
            timeout=_timeout(),
        )
        resp.raise_for_status()
        data = resp.json() or {}
        msg = data.get("message") or {}
        content = str(msg.get("content") or "").strip()
        return content or None
    except Exception as e:
        log.warning("Ollama chat request failed: %s", e)
        return None

