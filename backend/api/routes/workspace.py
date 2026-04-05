from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.schemas import (
    ConversationCreateRequest,
    ConversationRenameRequest,
    ConversationSummary,
    ConversationTurn,
    ConversationWorkspaceResponse,
    UserProfilePayload,
    WorkspaceBootstrapResponse,
)
from memory.conversation import (
    clear_conversation,
    delete_conversation,
    get_active_conversation_id,
    get_conversation_turns,
    get_user_profile,
    list_conversations,
    new_conversation,
    rename_conversation,
    set_active_conversation,
    set_user_profile,
)

router = APIRouter(tags=["workspace"])


def _profile_payload() -> UserProfilePayload:
    profile = get_user_profile() or {}
    return UserProfilePayload(
        name=str(profile.get("name") or ""),
        goal=str(profile.get("goal") or ""),
        mood=str(profile.get("mood") or "Focused"),
        communication_style=str(profile.get("communication_style") or "Friendly"),
        response_length=str(profile.get("response_length") or "Balanced"),
    )


def _conversation_summaries() -> tuple[list[ConversationSummary], int | None]:
    active_id = get_active_conversation_id()
    items = list_conversations()
    summaries = [
        ConversationSummary(
            id=int(item["id"]),
            title=str(item.get("title") or "Conversation"),
            created_at=str(item.get("created_at") or "") or None,
            messages=int(item.get("messages") or 0),
            is_active=int(item["id"]) == active_id,
        )
        for item in items
    ]
    return summaries, active_id


def _history_payload(conversation_id: int | None) -> list[ConversationTurn]:
    return [
        ConversationTurn(
            role=str(item.get("role") or ""),
            message=str(item.get("message") or ""),
            tool_kind=str(item.get("tool_kind") or "") or None,
            tool_payload=item.get("tool_payload"),
        )
        for item in get_conversation_turns(conversation_id=conversation_id)
    ]


def _ensure_conversation_exists(conversation_id: int) -> None:
    ids = {int(item["id"]) for item in list_conversations()}
    if int(conversation_id) not in ids:
        raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} does not exist.")


def _workspace_response(conversation_id: int | None = None) -> ConversationWorkspaceResponse:
    summaries, active_id = _conversation_summaries()
    selected_id = int(conversation_id) if conversation_id is not None else active_id
    return ConversationWorkspaceResponse(
        conversations=summaries,
        active_conversation_id=selected_id,
        history=_history_payload(selected_id),
    )


@router.get("/workspace/bootstrap", response_model=WorkspaceBootstrapResponse)
async def workspace_bootstrap() -> WorkspaceBootstrapResponse:
    workspace = _workspace_response()
    return WorkspaceBootstrapResponse(
        profile=_profile_payload(),
        conversations=workspace.conversations,
        active_conversation_id=workspace.active_conversation_id,
        history=workspace.history,
    )


@router.get("/profile", response_model=UserProfilePayload)
async def get_profile() -> UserProfilePayload:
    return _profile_payload()


@router.put("/profile", response_model=UserProfilePayload)
async def put_profile(payload: UserProfilePayload) -> UserProfilePayload:
    profile = payload.model_dump()
    set_user_profile(profile)
    return _profile_payload()


@router.post("/conversations", response_model=ConversationWorkspaceResponse)
async def create_conversation(payload: ConversationCreateRequest) -> ConversationWorkspaceResponse:
    conversation_id = new_conversation(payload.title, activate=True)
    return _workspace_response(conversation_id)


@router.post("/conversations/{conversation_id}/activate", response_model=ConversationWorkspaceResponse)
async def activate_conversation(conversation_id: int) -> ConversationWorkspaceResponse:
    _ensure_conversation_exists(conversation_id)
    try:
        set_active_conversation(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _workspace_response(conversation_id)


@router.patch("/conversations/{conversation_id}", response_model=ConversationWorkspaceResponse)
async def rename_conversation_route(
    conversation_id: int,
    payload: ConversationRenameRequest,
) -> ConversationWorkspaceResponse:
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title must not be empty")
    _ensure_conversation_exists(conversation_id)
    rename_conversation(conversation_id, title)
    return _workspace_response(conversation_id)


@router.post("/conversations/{conversation_id}/clear", response_model=ConversationWorkspaceResponse)
async def clear_conversation_route(conversation_id: int) -> ConversationWorkspaceResponse:
    _ensure_conversation_exists(conversation_id)
    clear_conversation(conversation_id=conversation_id)
    return _workspace_response(conversation_id)


@router.delete("/conversations/{conversation_id}", response_model=ConversationWorkspaceResponse)
async def delete_conversation_route(conversation_id: int) -> ConversationWorkspaceResponse:
    _ensure_conversation_exists(conversation_id)
    if len(list_conversations()) <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the only conversation.")
    delete_conversation(conversation_id)
    return _workspace_response()
