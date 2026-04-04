# backend/api/schemas.py
from __future__ import annotations
from pydantic import BaseModel, ConfigDict


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TranscribeResponse(_StrictModel):
    transcribed_text: str


class TranscribeBytesRequest(_StrictModel):
    audio_base64: str
    content_type: str | None = None
    filename: str | None = None


class ErrorResponse(_StrictModel):
    error: str


class StatusResponse(_StrictModel):
    listening: bool


class SimpleMessage(_StrictModel):
    ok: bool
    message: str


class ChatRequest(_StrictModel):
    user_text: str
    conversation_id: int | None = None
    mode: str | None = None
    context: str | None = None
    system_instructions: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    # NEW: controls for including server-side memory/profile
    use_history: bool = True
    history_window: int | None = None
    use_profile: bool = True
    speak_reply: bool = False


class ChatResponse(_StrictModel):
    reply: str
    mode_used: str
    conversation_id: int | None = None
    tts_url: str | None = None


class UserProfilePayload(_StrictModel):
    name: str = ""
    goal: str = ""
    mood: str = "Focused"
    communication_style: str = "Friendly"
    response_length: str = "Balanced"


class ConversationSummary(_StrictModel):
    id: int
    title: str
    created_at: str | None = None
    messages: int = 0
    is_active: bool = False


class ConversationTurn(_StrictModel):
    role: str
    message: str


class WorkspaceBootstrapResponse(_StrictModel):
    profile: UserProfilePayload
    conversations: list[ConversationSummary]
    active_conversation_id: int | None = None
    history: list[ConversationTurn]


class ConversationCreateRequest(_StrictModel):
    title: str | None = None


class ConversationRenameRequest(_StrictModel):
    title: str


class ConversationWorkspaceResponse(_StrictModel):
    conversations: list[ConversationSummary]
    active_conversation_id: int | None = None
    history: list[ConversationTurn]
