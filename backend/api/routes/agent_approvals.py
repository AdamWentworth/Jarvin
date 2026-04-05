from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.agent.chat.assistant_chat_tools import maybe_handle_assistant_tool_request
from backend.api.schemas import ApprovalDecisionRequest, ChatResponse
from memory.conversation import append_turn

router = APIRouter(tags=["agent-approvals"])


@router.post("/agent/approvals/respond", response_model=ChatResponse)
async def respond_to_agent_approval(payload: ApprovalDecisionRequest) -> ChatResponse:
    decision = (payload.decision or "").strip()
    if not decision:
        raise HTTPException(status_code=400, detail="empty approval decision")

    try:
        tool_response = maybe_handle_assistant_tool_request(
            decision,
            conversation_id=payload.conversation_id,
            client_session_id=payload.client_session_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not tool_response.handled:
        raise HTTPException(status_code=409, detail="No pending approval matched that response.")

    if getattr(tool_response, "persist_assistant_turn", True):
        append_turn(
            "assistant",
            tool_response.reply,
            conversation_id=payload.conversation_id,
            tool_kind=tool_response.tool_kind,
            tool_payload=tool_response.tool_payload,
        )
    return ChatResponse(
        reply=tool_response.reply,
        mode_used="agent_approval",
        conversation_id=payload.conversation_id,
        tool_kind=tool_response.tool_kind,
        tool_payload=tool_response.tool_payload,
    )
