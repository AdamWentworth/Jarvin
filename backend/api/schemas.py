# backend/api/schemas.py
from __future__ import annotations
from typing import Any
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
    agent_access_mode: str | None = None
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
    tool_kind: str | None = None
    tool_payload: dict[str, Any] | None = None


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
    tool_kind: str | None = None
    tool_payload: dict[str, Any] | None = None


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


class ReminderItem(_StrictModel):
    id: int
    title: str
    notes: str = ""
    due_at: str
    recurrence: str = "once"
    status: str = "pending"
    created_at: str | None = None
    updated_at: str | None = None
    completed_at: str | None = None
    is_routine: bool = False
    is_overdue: bool = False


class ReminderListResponse(_StrictModel):
    reminders: list[ReminderItem]


class ReminderCreateRequest(_StrictModel):
    title: str
    due_at: str
    recurrence: str = "once"
    notes: str = ""


class ReminderUpdateRequest(_StrictModel):
    title: str | None = None
    due_at: str | None = None
    recurrence: str | None = None
    notes: str | None = None
    status: str | None = None


class AgentToolsManifestResponse(_StrictModel):
    enabled: bool
    workspace_root: str
    commands: list[str]
    allowed_commands: list[str]
    writes_enabled: bool
    commands_enabled: bool


class AgentListRequest(_StrictModel):
    path: str = "."
    max_entries: int | None = None


class AgentListResponse(_StrictModel):
    path: str
    entries: list[str]


class AgentSearchRequest(_StrictModel):
    query: str
    path: str = "."
    glob: str | None = None
    max_results: int | None = None


class AgentSearchMatch(_StrictModel):
    path: str
    line: int
    text: str


class AgentSearchResponse(_StrictModel):
    query: str
    matches: list[AgentSearchMatch]
    truncated: bool = False


class AgentReadRequest(_StrictModel):
    path: str
    start_line: int = 1
    end_line: int | None = None


class AgentReadResponse(_StrictModel):
    path: str
    start_line: int
    end_line: int
    text: str
    truncated: bool = False


class AgentWriteRequest(_StrictModel):
    path: str
    content: str
    append: bool = False


class AgentWriteResponse(_StrictModel):
    path: str
    bytes_written: int
    append: bool = False


class AgentCommandRequest(_StrictModel):
    command: str


class AgentCommandResponse(_StrictModel):
    command: str
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
