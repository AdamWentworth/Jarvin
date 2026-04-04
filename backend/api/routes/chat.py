# backend/api/routes/chat.py
from __future__ import annotations

import asyncio
import logging
import os
from fastapi import APIRouter

from backend.api.schemas import ChatRequest, ChatResponse, ErrorResponse
from backend.ai_engine import build_context, build_jarvin_config, generate_reply
from backend.tts.engine import synth_to_wav
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

    cfg = build_jarvin_config(
        mode=payload.mode,
        system_instructions=payload.system_instructions,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
    )
    conversation_id = payload.conversation_id

    # Build compact context
    ctx_parts: list[str] = []
    if payload.use_profile:
        profile = get_user_profile()
    else:
        profile = {}

    if payload.use_history:
        history = get_conversation_history(conversation_id=conversation_id)
    else:
        history = []

    if profile or history:
        max_turns = payload.history_window if payload.history_window is not None else cfg.history_window
        ctx_parts.append(
            build_context(profile=profile, history=history, max_turns=max(1, int(max_turns)))
        )

    if payload.context:
        ctx_parts.append(payload.context.strip())

    context_str = "\n\n".join([c for c in ctx_parts if c]).strip() or None

    try:
        reply = generate_reply(text, cfg=cfg, context=context_str)
        tts_url = None
        if payload.speak_reply and reply.strip():
            try:
                tts_path = await asyncio.to_thread(synth_to_wav, reply)
                tts_url = f"/_temp/{os.path.basename(tts_path)}"
            except Exception as exc:
                log.exception("Reply speech synthesis failed: %s", exc)
        # Persist turn so subsequent requests have fresh context
        append_turn("user", text, conversation_id=conversation_id)
        append_turn("assistant", reply, conversation_id=conversation_id)
        return ChatResponse(
            reply=reply,
            mode_used=cfg.mode,
            conversation_id=conversation_id,
            tts_url=tts_url,
        )
    except Exception as e:
        log.exception("Chat generation failed: %s", e)
        return ErrorResponse(error="chat generation failed")
