# backend/llm/runtime_local.py
from __future__ import annotations
from typing import Optional
from backend.ai_engine import generate_reply

class LocalChat:
    """
    Adapter implementing LLMChatEngine using the currently configured LLM backend.
    Keeps the existing graceful fallback behavior intact.
    """
    def reply(self, user_text: str, *, context: Optional[str] = None) -> str:
        return generate_reply(user_text, context=context)
