from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.schemas import AgentActionLogEntry, AgentActionLogResponse
from memory.agent_action_log import list_agent_action_events

router = APIRouter(tags=["agent-actions"])


@router.get("/agent/actions", response_model=AgentActionLogResponse)
async def agent_action_log(limit: int = 50, conversation_id: int | None = None) -> AgentActionLogResponse:
    try:
        actions = list_agent_action_events(limit=limit, conversation_id=conversation_id)
        return AgentActionLogResponse(actions=[AgentActionLogEntry(**item) for item in actions])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
