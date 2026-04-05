from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Literal

import config as cfg

AgentAccessMode = Literal["read_only", "approve_risky", "full_access"]
RiskLevel = Literal["medium", "high"]
ApprovalActionKind = Literal["run_command", "write_file"]


@dataclass(frozen=True)
class PendingHostApproval:
    action: ApprovalActionKind
    title: str
    summary: str
    risk_level: RiskLevel
    command: str | None = None
    path: str | None = None
    content: str | None = None
    append: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=10))


_pending_host_approvals: dict[str, PendingHostApproval] = {}


def normalize_agent_access_mode(value: str | None) -> AgentAccessMode:
    normalized = str(value or cfg.settings.agent_default_access_mode or "").strip().lower()
    if normalized in {"read_only", "approve_risky", "full_access"}:
        return normalized  # type: ignore[return-value]
    return "approve_risky"


def set_pending_host_approval(conversation_id: int | None, action: PendingHostApproval) -> None:
    _pending_host_approvals[_key(conversation_id)] = action


def get_pending_host_approval(conversation_id: int | None) -> PendingHostApproval | None:
    key = _key(conversation_id)
    action = _pending_host_approvals.get(key)
    if action is None:
        return None
    if action.expires_at <= datetime.now(timezone.utc):
        _pending_host_approvals.pop(key, None)
        return None
    return action


def clear_pending_host_approval(conversation_id: int | None) -> None:
    _pending_host_approvals.pop(_key(conversation_id), None)


def build_approval_payload(
    pending: PendingHostApproval,
    *,
    access_mode: AgentAccessMode,
    status: str,
    can_approve: bool,
) -> dict[str, object]:
    details: list[str] = []
    if pending.command:
        details.append(f"Command: {pending.command}")
    if pending.path:
        details.append(f"Path: {pending.path}")
    if pending.content:
        preview = pending.content.strip().replace("\r\n", "\n")
        if len(preview) > 180:
            preview = preview[:177].rstrip() + "..."
        if preview:
            details.append(f"Preview: {preview}")
    if pending.action == "write_file":
        details.append("Mode: append" if pending.append else "Mode: overwrite")

    return {
        "status": status,
        "action_kind": pending.action,
        "title": pending.title,
        "summary": pending.summary,
        "risk_level": pending.risk_level,
        "details": details,
        "access_mode": access_mode,
        "can_approve": can_approve,
    }


def _key(conversation_id: int | None) -> str:
    return str(conversation_id) if conversation_id is not None else "__default__"
