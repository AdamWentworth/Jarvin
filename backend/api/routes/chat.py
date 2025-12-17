# backend/api/routes/chat.py
from __future__ import annotations

import logging
from fastapi import APIRouter

from backend.api.schemas import ChatRequest, ChatResponse, ErrorResponse
from backend.ai_engine import generate_reply, JarvinConfig, build_context
from memory.conversation import (
    get_conversation_history,
    get_user_profile,
    append_turn,
)

log = logging.getLogger("jarvin.routes.chat")
router = APIRouter(tags=["chat"])

@router.post("/chat", response_model=ChatResponse | ErrorResponse)
async def chat_endpoint(payload: ChatRequest) -> ChatResponse | ErrorResponse:
    """
    Conversational chat endpoint.
    We automatically include a compact context (user profile + last N turns) unless disabled.
    """
    text = (payload.user_text or "").strip()
    if not text:
        return ErrorResponse(error="empty user_text")

    # Optional style knobs
    base_cfg = JarvinConfig()
    cfg = JarvinConfig(
        system_instructions=(payload.system_instructions or base_cfg.system_instructions),
        temperature=payload.temperature if payload.temperature is not None else base_cfg.temperature,
        max_tokens=payload.max_tokens if payload.max_tokens is not None else base_cfg.max_tokens,
    )

    # Build compact context
    ctx_parts: list[str] = []
    if payload.use_profile:
        profile = get_user_profile()
    else:
        profile = {}

    if payload.use_history:
        history = get_conversation_history()
    else:
        history = []

    if profile or history:
        ctx_parts.append(
            build_context(profile=profile, history=history, max_turns=max(1, int(payload.history_window)))
        )

    if payload.context:
        ctx_parts.append(payload.context.strip())

    context_str = "\n\n".join([c for c in ctx_parts if c]).strip() or None

    try:
        reply = generate_reply(text, cfg=cfg, context=context_str)
        # Persist turn so subsequent requests have fresh context
        append_turn("user", text)
        append_turn("assistant", reply)
        return ChatResponse(reply=reply)
    except Exception as e:
        log.exception("Chat generation failed: %s", e)
        return ErrorResponse(error="chat generation failed")
