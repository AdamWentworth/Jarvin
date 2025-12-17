# backend/llm/runtime_local.py
from __future__ import annotations
from typing import Optional
from backend.ai_engine import generate_reply  # uses llama.cpp when available, with fallback

class LocalChat:
    """
    Adapter implementing LLMChatEngine using existing generate_reply().
    Keeps current behavior (llama.cpp attempt + graceful fallback) intact.
    """
    def reply(self, user_text: str, *, context: Optional[str] = None) -> str:
        return generate_reply(user_text, context=context)
