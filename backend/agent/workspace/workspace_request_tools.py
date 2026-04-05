from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from backend.ai_engine import build_jarvin_config, generate_reply

_WORKSPACE_KEYWORDS = (
    "repo",
    "repository",
    "codebase",
    "workspace",
    "file",
    "files",
    "folder",
    "directory",
    "path",
    "git",
    "pytest",
    "tests",
)

_FILE_VERBS = ("read", "open", "show", "view", "pull up", "display")
_LIST_HINTS = ("list", "show me files", "show files", "show me what's in", "what's in", "what is in", "inside", "contents of")
_SEARCH_HINTS = ("search", "find", "look through", "look in", "grep", "where is")
_RUN_HINTS = ("run", "execute", "show git", "what changed", "what branch", "recent commits", "run tests")
_FILE_PATH_RE = re.compile(r"(?P<path>[\w./\\-]+\.[\w.-]+)")
_LINE_RANGE_RE = re.compile(
    r"(?:lines?\s+(?P<start>\d+)(?:\s*(?:to|-)\s*(?P<end>\d+))?|from\s+line\s+(?P<start2>\d+)\s+to\s+(?P<end2>\d+))",
    re.IGNORECASE,
)
_DIR_PATH_RE = re.compile(r"(?:in|inside|of)\s+(?P<path>[\w./\\-]+)\b", re.IGNORECASE)


@dataclass(frozen=True)
class WorkspacePlan:
    is_workspace_request: bool
    action: str = "unknown"
    query: str | None = None
    path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    command: str | None = None
    content: str | None = None
    append: bool = False


@dataclass(frozen=True)
class WorkspaceConversationContext:
    last_action: str = "unknown"
    last_query: str | None = None
    last_path: str | None = None
    last_command: str | None = None
    last_start_line: int | None = None
    last_end_line: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=15))


_workspace_context: dict[str, WorkspaceConversationContext] = {}


def maybe_plan_workspace_request(text: str, *, conversation_id: int | None = None) -> WorkspacePlan | None:
    message = (text or "").strip()
    if not message:
        return None

    context = get_workspace_context(conversation_id)
    heuristic = _heuristic_plan(message, context=context)
    if heuristic is not None:
        return heuristic

    if not _looks_workspace_related(message, context=context):
        return None

    plan = _llm_plan_workspace_request(message, context=context)
    if not plan.is_workspace_request:
        return None
    return _resolve_contextual_references(plan, context=context)


def get_workspace_context(conversation_id: int | None) -> WorkspaceConversationContext | None:
    key = _context_key(conversation_id)
    context = _workspace_context.get(key)
    if context is None:
        return None
    if context.expires_at <= datetime.now(timezone.utc):
        _workspace_context.pop(key, None)
        return None
    return context


def remember_workspace_context(
    conversation_id: int | None,
    *,
    action: str,
    query: str | None = None,
    path: str | None = None,
    command: str | None = None,
    start_line: int | None = None,
    end_line: int | None = None,
) -> None:
    _workspace_context[_context_key(conversation_id)] = WorkspaceConversationContext(
        last_action=action or "unknown",
        last_query=query,
        last_path=path,
        last_command=command,
        last_start_line=start_line,
        last_end_line=end_line,
    )


def clear_workspace_context(conversation_id: int | None) -> None:
    _workspace_context.pop(_context_key(conversation_id), None)


def _context_key(conversation_id: int | None) -> str:
    return str(conversation_id) if conversation_id is not None else "__default__"


def _heuristic_plan(message: str, *, context: WorkspaceConversationContext | None) -> WorkspacePlan | None:
    lower = message.lower().strip()

    if context and lower in {"show me more", "show more", "continue", "keep going"} and context.last_action == "read_file" and context.last_path:
        next_start = (context.last_end_line or context.last_start_line or 1) + 1
        return WorkspacePlan(
            is_workspace_request=True,
            action="read_file",
            path=context.last_path,
            start_line=next_start,
        )

    if context and lower in {"open that file", "read that file", "show that file"} and context.last_path:
        return WorkspacePlan(
            is_workspace_request=True,
            action="read_file",
            path=context.last_path,
        )

    if context and lower in {"run that again", "run that", "do that again"} and context.last_command:
        return WorkspacePlan(
            is_workspace_request=True,
            action="run_command",
            command=context.last_command,
        )

    read_plan = _heuristic_read_plan(message)
    if read_plan is not None:
        return read_plan

    list_plan = _heuristic_list_plan(message)
    if list_plan is not None:
        return list_plan

    search_plan = _heuristic_search_plan(message)
    if search_plan is not None:
        return search_plan

    run_plan = _heuristic_run_plan(message)
    if run_plan is not None:
        return run_plan

    return None


def _heuristic_read_plan(message: str) -> WorkspacePlan | None:
    lower = message.lower()
    path_match = _FILE_PATH_RE.search(message)
    if not path_match:
        return None
    if not any(verb in lower for verb in _FILE_VERBS):
        return None
    start_line, end_line = _extract_line_range(message)
    return WorkspacePlan(
        is_workspace_request=True,
        action="read_file",
        path=path_match.group("path"),
        start_line=start_line,
        end_line=end_line,
    )


def _heuristic_list_plan(message: str) -> WorkspacePlan | None:
    lower = message.lower()
    if not any(hint in lower for hint in _LIST_HINTS):
        return None
    path_match = _DIR_PATH_RE.search(message)
    path = path_match.group("path") if path_match else "."
    if _looks_like_file_path(path):
        return None
    return WorkspacePlan(
        is_workspace_request=True,
        action="list_directory",
        path=path,
    )


def _heuristic_search_plan(message: str) -> WorkspacePlan | None:
    lower = message.lower()
    if "where is " in lower and ("defined" in lower or "used" in lower or "implemented" in lower):
        query = re.sub(r"^.*?where is\s+", "", message, flags=re.IGNORECASE)
        query = re.sub(r"\s+(?:defined|used|implemented).*$", "", query, flags=re.IGNORECASE)
        return WorkspacePlan(is_workspace_request=True, action="search_repo", query=_clean_text(query))

    if not any(hint in lower for hint in _SEARCH_HINTS):
        return None

    if any(token in lower for token in ("repo", "repository", "codebase", "workspace", "code")):
        query = re.sub(
            r"(?:(?:can you|could you|please)\s+)?(?:search|find|look through|look in)\s+(?:the\s+)?(?:repo|repository|codebase|workspace|code)\s+(?:for\s+)?",
            "",
            message,
            flags=re.IGNORECASE,
        )
        query = re.sub(r"\s+in\s+the\s+(?:repo|repository|codebase|workspace|code)$", "", query, flags=re.IGNORECASE)
        cleaned = _clean_text(query)
        if cleaned:
            return WorkspacePlan(is_workspace_request=True, action="search_repo", query=cleaned)
    return None


def _heuristic_run_plan(message: str) -> WorkspacePlan | None:
    lower = message.lower().strip()

    explicit_git = re.search(r"\bgit\s+(status|diff(?:\s+--stat)?|branch|show\s+\S+|log(?:\s+--oneline(?:\s+-n\s+\d+)?)?)", message, re.IGNORECASE)
    if explicit_git:
        return WorkspacePlan(is_workspace_request=True, action="run_command", command=_clean_text(explicit_git.group(0)))

    if lower.startswith(("run ", "execute ")):
        command = re.sub(r"^(?:run|execute)\s+", "", message, flags=re.IGNORECASE)
        return WorkspacePlan(is_workspace_request=True, action="run_command", command=_clean_text(command))

    if "what changed" in lower or "show me what changed" in lower:
        return WorkspacePlan(is_workspace_request=True, action="run_command", command="git diff --stat")
    if "what branch" in lower or "which branch" in lower:
        return WorkspacePlan(is_workspace_request=True, action="run_command", command="git branch")
    if "recent commits" in lower or "latest commits" in lower:
        return WorkspacePlan(is_workspace_request=True, action="run_command", command="git log --oneline -n 10")
    if "backend tests" in lower:
        return WorkspacePlan(is_workspace_request=True, action="run_command", command="pytest tests/backend -q")
    if "api tests" in lower:
        return WorkspacePlan(is_workspace_request=True, action="run_command", command="pytest tests/backend/api -q")
    if "all tests" in lower or "full test suite" in lower:
        return WorkspacePlan(is_workspace_request=True, action="run_command", command="pytest -q")
    return None


def _looks_workspace_related(message: str, *, context: WorkspaceConversationContext | None) -> bool:
    lower = message.lower()
    if any(token in lower for token in _WORKSPACE_KEYWORDS):
        return True
    if _FILE_PATH_RE.search(message):
        return True
    if any(hint in lower for hint in _RUN_HINTS):
        return True
    if context is None:
        return False
    return any(token in lower for token in ("that file", "show more", "continue", "run that"))


def _llm_plan_workspace_request(message: str, *, context: WorkspaceConversationContext | None) -> WorkspacePlan:
    system = (
        "You extract safe workspace tool arguments for Jarvin. "
        "Return JSON only with keys: is_workspace_request (boolean), action (string), query (string|null), "
        "path (string|null), start_line (integer|null), end_line (integer|null), command (string|null). "
        "Valid actions are search_repo, read_file, list_directory, run_command, unknown. "
        "Prefer search_repo over raw rg commands when the user wants codebase search. "
        "Allowed commands are limited to: pytest ..., git status, git diff, git diff --stat, git log --oneline -n N, git branch, git show <rev>. "
        "If the user asks to run backend tests, command can be 'pytest tests/backend -q'. "
        "If the user asks what changed, command can be 'git diff --stat'. "
        "If the user refers to a prior file with 'that file', path may be null so Jarvin can use context. "
        "Do not answer the request itself."
    )
    prompt = (
        "Recent workspace context:\n"
        f"last_action={context.last_action if context else ''}\n"
        f"last_query={context.last_query if context else ''}\n"
        f"last_path={context.last_path if context else ''}\n"
        f"last_command={context.last_command if context else ''}\n"
        f"last_end_line={context.last_end_line if context else ''}\n\n"
        f"User message:\n{message}"
    )
    cfg_obj = build_jarvin_config(
        mode="agent_strong",
        system_instructions=system,
        temperature=0.1,
        max_tokens=240,
    )
    raw = generate_reply(prompt, cfg=cfg_obj, context=None)
    data = _parse_json_object(raw)
    return WorkspacePlan(
        is_workspace_request=bool(data.get("is_workspace_request")),
        action=str(data.get("action") or "unknown").strip().lower(),
        query=_clean_text(data.get("query")),
        path=_clean_text(data.get("path")),
        start_line=_coerce_int(data.get("start_line")),
        end_line=_coerce_int(data.get("end_line")),
        command=_clean_text(data.get("command")),
    )


def _resolve_contextual_references(plan: WorkspacePlan, *, context: WorkspaceConversationContext | None) -> WorkspacePlan:
    if context is None:
        return plan

    path = plan.path
    command = plan.command
    if not path and plan.action == "read_file":
        path = context.last_path
    if not command and plan.action == "run_command":
        command = context.last_command

    start_line = plan.start_line
    end_line = plan.end_line
    if plan.action == "read_file" and path == context.last_path and start_line is None and _looks_like_continue_request(context, plan):
        start_line = (context.last_end_line or context.last_start_line or 1) + 1

    return WorkspacePlan(
        is_workspace_request=plan.is_workspace_request,
        action=plan.action,
        query=plan.query or context.last_query,
        path=path,
        start_line=start_line,
        end_line=end_line,
        command=command,
    )


def _looks_like_continue_request(context: WorkspaceConversationContext, plan: WorkspacePlan) -> bool:
    return context.last_action == "read_file" and plan.path == context.last_path


def _extract_line_range(message: str) -> tuple[int | None, int | None]:
    match = _LINE_RANGE_RE.search(message)
    if not match:
        return None, None
    start_text = match.group("start") or match.group("start2")
    end_text = match.group("end") or match.group("end2")
    start_line = int(start_text) if start_text else None
    end_line = int(end_text) if end_text else None
    return start_line, end_line


def _coerce_int(value: object) -> int | None:
    if value in (None, "", False):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _looks_like_file_path(path: str) -> bool:
    return "." in PathLike(path).name if path else False


class PathLike(str):
    @property
    def name(self) -> str:
        return self.replace("\\", "/").rstrip("/").split("/")[-1]


def _parse_json_object(text: str) -> dict[str, object]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}


def _clean_text(value: object) -> str | None:
    cleaned = str(value or "").strip().rstrip("?.!,")
    return cleaned or None
