from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Literal

TaskRiskLevel = Literal["low", "medium", "high"]
TaskStepStatus = Literal["pending", "running", "completed", "failed", "blocked"]


@dataclass(frozen=True)
class HostTaskStepPlan:
    step_id: str
    title: str
    action_kind: str
    query: str | None = None
    path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    command: str | None = None
    content: str | None = None
    append: bool = False
    preview_block: str | None = None
    risk_level: TaskRiskLevel = "low"


@dataclass(frozen=True)
class PendingHostTask:
    title: str
    summary: str
    risk_level: TaskRiskLevel
    steps: tuple[HostTaskStepPlan, ...]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=15))


_pending_host_tasks: dict[str, PendingHostTask] = {}
_running_host_tasks: dict[str, PendingHostTask] = {}


def set_pending_host_task(conversation_id: int | None, task: PendingHostTask) -> None:
    _pending_host_tasks[_conversation_key(conversation_id)] = task


def get_pending_host_task(conversation_id: int | None) -> PendingHostTask | None:
    key = _conversation_key(conversation_id)
    task = _pending_host_tasks.get(key)
    if task is None:
        return None
    if task.expires_at <= datetime.now(timezone.utc):
        _pending_host_tasks.pop(key, None)
        return None
    return task


def clear_pending_host_task(conversation_id: int | None) -> None:
    _pending_host_tasks.pop(_conversation_key(conversation_id), None)


def set_running_host_task(conversation_id: int | None, task: PendingHostTask) -> None:
    _running_host_tasks[_conversation_key(conversation_id)] = task


def get_running_host_task(conversation_id: int | None) -> PendingHostTask | None:
    return _running_host_tasks.get(_conversation_key(conversation_id))


def clear_running_host_task(conversation_id: int | None) -> None:
    _running_host_tasks.pop(_conversation_key(conversation_id), None)


def build_host_task_payload(
    task: PendingHostTask,
    *,
    access_mode: str,
    status: str,
    can_approve: bool,
    details: list[str] | None = None,
    steps: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "status": status,
        "title": task.title,
        "summary": task.summary,
        "risk_level": task.risk_level,
        "access_mode": access_mode,
        "can_approve": can_approve,
        "details": details or [],
        "steps": steps if steps is not None else [_step_payload(step) for step in task.steps],
        "total_steps": len(task.steps),
        "completed_steps": sum(1 for step in (steps or []) if str(step.get("status") or "") == "completed") if steps else 0,
    }


def build_host_task_step_result(
    step: HostTaskStepPlan,
    *,
    status: TaskStepStatus,
    detail: str | None = None,
    preview_block: str | None = None,
) -> dict[str, object]:
    payload = _step_payload(step)
    payload["status"] = status
    if detail:
        payload["detail"] = detail
    final_preview = preview_block or step.preview_block
    if final_preview:
        payload["preview_block"] = final_preview
    return payload


def _step_payload(step: HostTaskStepPlan) -> dict[str, object]:
    payload = {
        "step_id": step.step_id,
        "title": step.title,
        "action_kind": step.action_kind,
        "risk_level": step.risk_level,
        "status": "pending",
        "path": step.path,
        "query": step.query,
        "command": step.command,
        "append": step.append,
    }
    if step.preview_block:
        payload["preview_block"] = step.preview_block
    return payload


def _conversation_key(conversation_id: int | None) -> str:
    return str(conversation_id) if conversation_id is not None else "__default__"
