from __future__ import annotations

import json
import re
from dataclasses import dataclass

import backend.agent.host_tool_runtime as host_tool_runtime
from backend.agent.workspace.workspace_request_tools import WorkspacePlan, maybe_plan_workspace_request
from backend.ai_engine import build_jarvin_config, generate_reply

_TASK_VERBS = (
    "investigate",
    "look into",
    "debug",
    "review",
    "analyze",
    "check why",
    "figure out",
    "work on",
    "trace",
    "inspect",
    "walk me through",
)
_STEP_SPLIT_RE = re.compile(r"\b(?:and then|then|also|after that)\b", re.IGNORECASE)
_WORKSPACE_RELATED_RE = re.compile(r"\b(?:repo|repository|codebase|workspace|file|folder|directory|path|git|pytest|tests)\b", re.IGNORECASE)
_WRITE_WITH_CONTENT_RE = re.compile(
    r"(?P<verb>write|create|save|put|append)\s+(?:(?:to|into)\s+)?(?P<path>[\w./\\-]+)\s+(?:with|containing|that says|saying)\s+(?P<content>.+)",
    re.IGNORECASE,
)
_WRITE_SUMMARY_RE = re.compile(
    r"(?:(?:write|create|save|put)\s+(?:a\s+)?)?(?:summary|notes?|report|results?)\s+(?:to|in|into)\s+(?P<path>[\w./\\-]+)",
    re.IGNORECASE,
)
_APPEND_PREFIX_RE = re.compile(r"^(?:append|add)\b", re.IGNORECASE)


@dataclass(frozen=True)
class PlannedHostTask:
    is_task_request: bool
    title: str
    summary: str
    steps: tuple[WorkspacePlan, ...]


def maybe_plan_host_task_request(text: str, *, conversation_id: int | None = None) -> PlannedHostTask | None:
    message = (text or "").strip()
    if not message:
        return None

    heuristic = _heuristic_task_plan(message, conversation_id=conversation_id)
    if heuristic is not None:
        return heuristic

    if not _looks_like_high_level_task(message):
        return None

    llm_plan = _llm_task_plan(message, conversation_id=conversation_id)
    if llm_plan is None or not llm_plan.steps:
        return None
    return llm_plan


def _heuristic_task_plan(message: str, *, conversation_id: int | None) -> PlannedHostTask | None:
    parts = [part.strip(" ,.") for part in _STEP_SPLIT_RE.split(message) if part.strip(" ,.")]
    if len(parts) < 2:
        return None

    steps: list[WorkspacePlan] = []
    for part in parts:
        plan = _plan_task_step(part, conversation_id=conversation_id)
        if plan is None or not plan.is_workspace_request or str(plan.action or "").strip().lower() == "unknown":
            return None
        steps.append(plan)

    if len(steps) < 2:
        return None

    title = "Host workspace task"
    summary = f"Execute {len(steps)} host-side workspace steps for: `{message}`."
    return PlannedHostTask(
        is_task_request=True,
        title=title,
        summary=summary,
        steps=tuple(steps[:4]),
    )


def _looks_like_high_level_task(message: str) -> bool:
    lower = message.lower()
    return bool(_WORKSPACE_RELATED_RE.search(message) and any(verb in lower for verb in _TASK_VERBS))


def _llm_task_plan(message: str, *, conversation_id: int | None) -> PlannedHostTask | None:
    system = (
        "You plan small safe host tasks for Jarvin. "
        "Return JSON only with keys: is_task_request (boolean), title (string), summary (string), steps (array). "
        "Each step object may use only these actions: search_repo, read_file, list_directory, run_command, write_file. "
        "Allowed run_command values are limited to safe Jarvin commands such as git status, git diff --stat, git log --oneline -n 10, git branch, git show <rev>, pytest ..., rg .... "
        "Each step may include title, action, query, path, start_line, end_line, command, content, append. "
        "For write_file, content should be either the exact text to write or the literal token {{previous_results}} when the user wants a short summary file based on earlier task steps. "
        "Plan at most 4 steps. Prefer read/search/list over commands when possible. "
        "Do not answer the user's task."
    )
    cfg_obj = build_jarvin_config(
        mode="agent_strong",
        system_instructions=system,
        temperature=0.1,
        max_tokens=320,
    )
    prompt = (
        f"Conversation id: {conversation_id}\n"
        f"User task:\n{message}"
    )
    raw = generate_reply(prompt, cfg=cfg_obj, context=None)
    data = _parse_json_object(raw)
    if not bool(data.get("is_task_request")):
        return None

    steps: list[WorkspacePlan] = []
    for item in data.get("steps") or []:
        if not isinstance(item, dict):
            continue
        action = str(item.get("action") or "").strip().lower()
        if action not in {"search_repo", "read_file", "list_directory", "run_command", "write_file"}:
            continue
        plan = WorkspacePlan(
            is_workspace_request=True,
            action=action,
            query=_clean_text(item.get("query")),
            path=_clean_text(item.get("path")),
            start_line=_coerce_int(item.get("start_line")),
            end_line=_coerce_int(item.get("end_line")),
            command=_clean_command(item.get("command")) if action == "run_command" else None,
            content=_clean_multiline_text(item.get("content")) if action == "write_file" else None,
            append=bool(item.get("append")) if action == "write_file" else False,
        )
        if _validate_step(plan):
            steps.append(plan)
        if len(steps) >= 4:
            break

    if not steps:
        return None

    return PlannedHostTask(
        is_task_request=True,
        title=_clean_text(data.get("title")) or "Host workspace task",
        summary=_clean_text(data.get("summary")) or f"Execute {len(steps)} host-side workspace steps.",
        steps=tuple(steps),
    )


def _validate_step(plan: WorkspacePlan) -> bool:
    action = str(plan.action or "").strip().lower()
    if action == "search_repo":
        return bool(_clean_text(plan.query))
    if action == "read_file":
        return bool(_clean_text(plan.path))
    if action == "list_directory":
        return True
    if action == "run_command":
        command = _clean_command(plan.command)
        if not command:
            return False
        try:
            host_tool_runtime.describe_safe_command(command)
        except Exception:
            return False
        return True
    if action == "write_file":
        path = _clean_text(plan.path)
        content = _clean_multiline_text(plan.content)
        if not path or not content:
            return False
        try:
            host_tool_runtime.resolve_workspace_path(path)
        except Exception:
            return False
        return True
    return False


def _clean_command(value: object) -> str | None:
    text = _clean_text(value)
    return text


def _plan_task_step(message: str, *, conversation_id: int | None) -> WorkspacePlan | None:
    workspace_plan = maybe_plan_workspace_request(message, conversation_id=conversation_id)
    if workspace_plan is not None:
        return workspace_plan
    return _heuristic_write_step(message)


def _heuristic_write_step(message: str) -> WorkspacePlan | None:
    content_match = _WRITE_WITH_CONTENT_RE.search(message)
    if content_match:
        verb = str(content_match.group("verb") or "").strip().lower()
        path = _clean_text(content_match.group("path"))
        content = _clean_multiline_text(content_match.group("content"))
        if path and content:
            return WorkspacePlan(
                is_workspace_request=True,
                action="write_file",
                path=path,
                content=content,
                append=verb in {"append", "add"},
            )

    summary_match = _WRITE_SUMMARY_RE.search(message)
    if summary_match:
        path = _clean_text(summary_match.group("path"))
        if path:
            return WorkspacePlan(
                is_workspace_request=True,
                action="write_file",
                path=path,
                content="{{previous_results}}",
                append=bool(_APPEND_PREFIX_RE.search(message)),
            )

    return None


def _clean_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _clean_multiline_text(value: object) -> str | None:
    text = str(value or "").replace("\r\n", "\n").strip()
    return text or None


def _coerce_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except Exception:
        return None


def _parse_json_object(raw: str) -> dict[str, object]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        try:
            data = json.loads(text[start : end + 1])
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
