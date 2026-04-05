from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Literal

import config as cfg

AgentAccessMode = Literal["read_only", "approve_risky", "full_access"]
RiskLevel = Literal["medium", "high"]
ApprovalActionKind = Literal["run_command", "write_file"]
TrustScope = Literal["conversation", "session"]


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


@dataclass(frozen=True)
class HostActionTrustGrant:
    action: ApprovalActionKind
    scope: TrustScope = "conversation"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=30))


_pending_host_approvals: dict[str, PendingHostApproval] = {}
_conversation_action_trust: dict[str, dict[ApprovalActionKind, HostActionTrustGrant]] = {}
_session_action_trust: dict[str, dict[ApprovalActionKind, HostActionTrustGrant]] = {}


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


def grant_host_action_trust(
    conversation_id: int | None,
    client_session_id: str | None,
    action: ApprovalActionKind,
    *,
    scope: TrustScope = "conversation",
) -> HostActionTrustGrant:
    key = _conversation_key(conversation_id) if scope == "conversation" else _session_key(client_session_id)
    grant = HostActionTrustGrant(action=action, scope=scope)
    trust_store = _conversation_action_trust if scope == "conversation" else _session_action_trust
    trust_by_action = trust_store.setdefault(key, {})
    trust_by_action[action] = grant
    return grant


def get_host_action_trust(
    conversation_id: int | None,
    client_session_id: str | None,
    action: ApprovalActionKind,
) -> HostActionTrustGrant | None:
    for scope, store, key in (
        ("conversation", _conversation_action_trust, _conversation_key(conversation_id)),
        ("session", _session_action_trust, _session_key(client_session_id)),
    ):
        grant = _get_active_trust(store, key, action)
        if grant is not None:
            return grant
    return None


def clear_host_action_trust(
    conversation_id: int | None,
    client_session_id: str | None = None,
    action: ApprovalActionKind | None = None,
    *,
    scope: TrustScope | None = None,
) -> None:
    if scope in {None, "conversation"}:
        _clear_trust_store(_conversation_action_trust, _conversation_key(conversation_id), action)
    if scope in {None, "session"}:
        _clear_trust_store(_session_action_trust, _session_key(client_session_id), action)


def build_approval_payload(
    pending: PendingHostApproval,
    *,
    access_mode: AgentAccessMode,
    status: str,
    can_approve: bool,
    can_trust_conversation: bool = False,
    can_trust_session: bool = False,
    trust_active: bool = False,
    trust_scope: TrustScope | None = None,
    extra_details: list[str] | None = None,
    preview_block: str | None = None,
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
    if extra_details:
        details.extend([str(item).strip() for item in extra_details if str(item).strip()])

    return {
        "status": status,
        "action_kind": pending.action,
        "title": pending.title,
        "summary": pending.summary,
        "risk_level": pending.risk_level,
        "details": details,
        "access_mode": access_mode,
        "can_approve": can_approve,
        "can_trust_conversation": can_trust_conversation,
        "can_trust_session": can_trust_session,
        "trust_active": trust_active,
        "trust_scope": trust_scope,
        "preview_block": preview_block,
    }


def _conversation_key(conversation_id: int | None) -> str:
    return str(conversation_id) if conversation_id is not None else "__default__"


def _key(conversation_id: int | None) -> str:
    return _conversation_key(conversation_id)


def _session_key(client_session_id: str | None) -> str:
    value = str(client_session_id or "").strip()
    return value or "__default_session__"


def _get_active_trust(
    trust_store: dict[str, dict[ApprovalActionKind, HostActionTrustGrant]],
    key: str,
    action: ApprovalActionKind,
) -> HostActionTrustGrant | None:
    trust_by_action = trust_store.get(key)
    if not trust_by_action:
        return None
    grant = trust_by_action.get(action)
    if grant is None:
        return None
    if grant.expires_at <= datetime.now(timezone.utc):
        trust_by_action.pop(action, None)
        if not trust_by_action:
            trust_store.pop(key, None)
        return None
    return grant


def _clear_trust_store(
    trust_store: dict[str, dict[ApprovalActionKind, HostActionTrustGrant]],
    key: str,
    action: ApprovalActionKind | None,
) -> None:
    if action is None:
        trust_store.pop(key, None)
        return
    trust_by_action = trust_store.get(key)
    if not trust_by_action:
        return
    trust_by_action.pop(action, None)
    if not trust_by_action:
        trust_store.pop(key, None)
