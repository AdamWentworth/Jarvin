from __future__ import annotations

import logging
from typing import Optional

import config as cfg
from backend.llm import runtime_ollama
from backend.llm.runtime_llama_cpp import chat_completion as llama_chat_completion

log = logging.getLogger("jarvin.llm.router")


def current_backend() -> str:
    return str(cfg.settings.llm_backend or "llama_cpp").strip().lower()


def chat_completion(
    system_prompt: str,
    user_text: str,
    temperature: float = 0.7,
    max_tokens: int = 256,
) -> Optional[str]:
    backend = current_backend()
    if backend == "ollama_http":
        return runtime_ollama.chat_completion(
            system_prompt=system_prompt,
            user_text=user_text,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if backend != "llama_cpp":
        log.warning("Unknown llm backend '%s'; falling back to llama_cpp.", backend)

    return llama_chat_completion(
        system_prompt=system_prompt,
        user_text=user_text,
        temperature=temperature,
        max_tokens=max_tokens,
    )
