from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import config as cfg

REPO_ROOT = Path(__file__).resolve().parents[2]
MAX_COMMAND_OUTPUT_CHARS = 12_000
DEFAULT_LIST_LIMIT = 200


class AgentToolsDisabledError(RuntimeError):
    pass


@dataclass(frozen=True)
class SearchMatch:
    path: str
    line: int
    text: str


@dataclass(frozen=True)
class SearchResult:
    query: str
    matches: list[SearchMatch]
    truncated: bool


@dataclass(frozen=True)
class ReadResult:
    path: str
    start_line: int
    end_line: int
    text: str
    truncated: bool


@dataclass(frozen=True)
class WriteResult:
    path: str
    bytes_written: int
    append: bool


@dataclass(frozen=True)
class CommandResult:
    command: str
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool


def ensure_tools_enabled() -> None:
    if not cfg.settings.agent_tools_enabled:
        raise AgentToolsDisabledError("Agent tools are disabled in this Jarvin host.")


def workspace_root() -> Path:
    raw = str(cfg.settings.agent_workspace_root or ".").strip() or "."
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = (REPO_ROOT / candidate).resolve()
    else:
        candidate = candidate.resolve()
    candidate.relative_to(REPO_ROOT.resolve())
    return candidate


def resolve_workspace_path(relative_path: str | None = None) -> Path:
    ensure_tools_enabled()
    root = workspace_root()
    raw = str(relative_path or ".").strip() or "."
    target = (root / raw).resolve()
    target.relative_to(root)
    return target


def manifest() -> dict[str, object]:
    ensure_tools_enabled()
    return {
        "enabled": True,
        "workspace_root": str(workspace_root()),
        "commands": [
            "/tool help",
            "/tool ls [path]",
            "/tool search <query>",
            "/tool read <path> [start_line] [end_line]",
            "/tool write <path> then put file contents on the next lines",
            "/tool append <path> then put extra file contents on the next lines",
            "/tool run <allowed command>",
            "/tool web <query>",
            "/tool google <query>",
            "/tool weather <location>",
            "/tool calendar [days]",
            "/tool calendar auth",
        ],
        "allowed_commands": [
            "rg ...",
            "pytest ...",
            "git status",
            "git diff [--stat|-- <path>]",
            "git log [--oneline -n N]",
            "git branch",
            "git show <rev>",
        ],
        "writes_enabled": cfg.settings.agent_allow_file_writes,
        "commands_enabled": cfg.settings.agent_allow_command_execution,
    }


def list_directory(path: str = ".", *, max_entries: int = DEFAULT_LIST_LIMIT) -> list[str]:
    target = resolve_workspace_path(path)
    if not target.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    if not target.is_dir():
        raise ValueError(f"Path is not a directory: {path}")

    entries = sorted(
        target.iterdir(),
        key=lambda item: (not item.is_dir(), item.name.lower()),
    )
    out: list[str] = []
    for item in entries[: max(1, max_entries)]:
        marker = "/" if item.is_dir() else ""
        rel = item.relative_to(workspace_root()).as_posix()
        out.append(f"{rel}{marker}")
    return out


def search_workspace(
    query: str,
    *,
    path: str = ".",
    glob: str | None = None,
    max_results: int | None = None,
) -> SearchResult:
    ensure_tools_enabled()
    q = str(query or "").strip()
    if not q:
        raise ValueError("Search query cannot be empty.")

    target = resolve_workspace_path(path)
    limit = max(1, min(int(max_results or cfg.settings.agent_max_search_results), 500))
    cmd = ["rg", "--line-number", "--no-heading", "--color", "never", "--smart-case", q, str(target)]
    if glob:
        cmd.extend(["-g", glob])

    try:
        proc = subprocess.run(
            cmd,
            cwd=workspace_root(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=cfg.settings.agent_command_timeout_sec,
            shell=False,
        )
        stdout = proc.stdout or ""
    except FileNotFoundError:
        stdout = _python_search_fallback(q, target)

    matches: list[SearchMatch] = []
    for line in stdout.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        rel_path = _normalize_path(parts[0])
        try:
            line_no = int(parts[1])
        except ValueError:
            continue
        matches.append(SearchMatch(path=rel_path, line=line_no, text=parts[2]))
        if len(matches) >= limit:
            break

    truncated = len(matches) >= limit and len(stdout.splitlines()) > limit
    return SearchResult(query=q, matches=matches, truncated=truncated)


def read_file(path: str, *, start_line: int = 1, end_line: int | None = None) -> ReadResult:
    target = resolve_workspace_path(path)
    if not target.exists():
        raise FileNotFoundError(f"File does not exist: {path}")
    if not target.is_file():
        raise ValueError(f"Path is not a file: {path}")

    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, int(start_line))
    max_lines = max(1, int(cfg.settings.agent_max_file_read_lines))
    requested_end = int(end_line) if end_line is not None else min(len(lines), start + max_lines - 1)
    end = max(start, min(len(lines), requested_end, start + max_lines - 1))
    if not lines:
        end = start
    snippet = lines[start - 1 : end]
    text = "\n".join(f"{start + index}: {line}" for index, line in enumerate(snippet))
    truncated = end_line is None and len(snippet) < max(0, len(lines) - start + 1)
    return ReadResult(
        path=_normalize_path(target),
        start_line=start,
        end_line=end,
        text=text,
        truncated=truncated,
    )


def write_file(path: str, content: str, *, append: bool = False) -> WriteResult:
    ensure_tools_enabled()
    if not cfg.settings.agent_allow_file_writes:
        raise PermissionError("File writes are disabled on this Jarvin host.")

    target = resolve_workspace_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    text = content or ""
    with target.open(mode, encoding="utf-8", newline="") as handle:
        handle.write(text)
    return WriteResult(path=_normalize_path(target), bytes_written=len(text.encode("utf-8")), append=append)


def run_safe_command(command: str) -> CommandResult:
    ensure_tools_enabled()
    if not cfg.settings.agent_allow_command_execution:
        raise PermissionError("Command execution is disabled on this Jarvin host.")

    raw = str(command or "").strip()
    if not raw:
        raise ValueError("Command cannot be empty.")
    if any(token in raw for token in ["&&", "||", "|", ">", "<", ";"]):
        raise ValueError("Shell operators are not allowed in agent commands.")

    argv = shlex.split(raw, posix=False)
    if not argv:
        raise ValueError("Command cannot be empty.")

    _validate_command(argv)

    try:
        proc = subprocess.run(
            argv,
            cwd=workspace_root(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=cfg.settings.agent_command_timeout_sec,
            shell=False,
        )
        return CommandResult(
            command=raw,
            returncode=proc.returncode,
            stdout=_trim_output(proc.stdout or ""),
            stderr=_trim_output(proc.stderr or ""),
            timed_out=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command=raw,
            returncode=124,
            stdout=_trim_output((exc.stdout or "") if isinstance(exc.stdout, str) else ""),
            stderr=_trim_output((exc.stderr or "") if isinstance(exc.stderr, str) else "Command timed out."),
            timed_out=True,
        )


def _validate_command(argv: list[str]) -> None:
    program = argv[0].lower()
    if program == "rg":
        return
    if program == "pytest":
        return
    if program != "git":
        raise ValueError("Allowed commands are limited to rg, pytest, and a small set of git reads.")

    if len(argv) < 2:
        raise ValueError("Git subcommand is required.")

    subcommand = argv[1].lower()
    allowed = {"status", "diff", "log", "branch", "show"}
    if subcommand not in allowed:
        raise ValueError(f"Git subcommand '{subcommand}' is not allowed.")


def _normalize_path(path_like: str | Path) -> str:
    path = Path(path_like).resolve()
    try:
        return path.relative_to(workspace_root()).as_posix()
    except ValueError:
        return path.as_posix()


def _trim_output(text: str) -> str:
    if len(text) <= MAX_COMMAND_OUTPUT_CHARS:
        return text
    suffix = "\n...[truncated]..."
    return text[: max(0, MAX_COMMAND_OUTPUT_CHARS - len(suffix))] + suffix


def _python_search_fallback(query: str, target: Path) -> str:
    lines: list[str] = []
    for path in _iter_text_files(target):
        try:
            content = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        rel = _normalize_path(path)
        for index, line in enumerate(content, start=1):
            if query.lower() in line.lower():
                lines.append(f"{rel}:{index}:{line}")
    return "\n".join(lines)


def _iter_text_files(target: Path) -> Iterable[Path]:
    if target.is_file():
        yield target
        return

    for root, dirs, files in os.walk(target):
        dirs[:] = [name for name in dirs if name not in {".git", ".venv", "node_modules", "__pycache__"}]
        for filename in files:
            if filename.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".exe", ".dll", ".so", ".wav", ".mp3", ".webm", ".apk")):
                continue
            yield Path(root) / filename
