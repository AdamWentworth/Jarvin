from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

import config as cfg
from backend.agent import tools
from backend.agent.external_tools import (
    begin_google_calendar_auth,
    get_calendar_agenda,
    get_weather,
    google_calendar_credentials_configured,
    google_calendar_token_available,
    google_search_is_configured,
    search_web,
)

_WEATHER_RE = re.compile(
    r"(?:what(?:'s| is)\s+the\s+weather|weather|forecast)(?:\s+(?:like|for|in|at))?\s+(?P<location>.+)$",
    re.IGNORECASE,
)
_WEB_SEARCH_RE = re.compile(
    r"(?:(?:can you|could you|please)\s+)?(?:search(?:\s+the\s+web)?\s+for|look up|find information on)\s+(?P<query>.+)$",
    re.IGNORECASE,
)
_GOOGLE_RE = re.compile(
    r"(?:(?:can you|could you|please)\s+)?google\s+(?P<query>.+)$",
    re.IGNORECASE,
)
_CALENDAR_AUTH_RE = re.compile(
    r"(?:connect|set up|setup|authorize|auth|link).*(?:google\s+calendar|calendar)|(?:google\s+calendar|calendar).*(?:connect|set up|setup|authorize|auth|link)",
    re.IGNORECASE,
)
_CALENDAR_LOOKUP_RE = re.compile(
    r"(?:what(?:'s| is)\s+on\s+(?:my\s+)?(?:calendar|schedule)|show\s+(?:my\s+)?(?:calendar|schedule)|(?:my\s+)?agenda\b|do i have anything\b)",
    re.IGNORECASE,
)
_REPO_SEARCH_RE = re.compile(
    r"(?:(?:search|find)\s+(?:the\s+)?(?:repo|repository|codebase|workspace)\s+(?:for\s+)?)?(?P<query>.+?)\s+(?:in\s+(?:the\s+)?(?:repo|repository|codebase|workspace))$",
    re.IGNORECASE,
)
_READ_FILE_RE = re.compile(
    r"(?:(?:read|open|show)\s+(?:me\s+)?)`?(?P<path>[\w./\\-]+\.[\w.-]+)`?(?:\s+lines?\s+(?P<start>\d+)(?:\s*(?:to|-)\s*(?P<end>\d+))?)?$",
    re.IGNORECASE,
)
_LIST_DIR_RE = re.compile(
    r"(?:(?:list|show)\s+(?:files|contents)(?:\s+in)?\s+)(?P<path>[\w./\\-]+)$",
    re.IGNORECASE,
)
_RUN_RE = re.compile(
    r"(?:(?:please\s+)?(?:run|execute))\s+(?P<command>.+)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ToolChatResponse:
    handled: bool
    reply: str = ""


def maybe_handle_assistant_tool_request(text: str) -> ToolChatResponse:
    explicit = maybe_handle_tool_command(text)
    if explicit.handled:
        return explicit
    return maybe_handle_natural_language_tool_request(text)


def maybe_handle_tool_command(text: str) -> ToolChatResponse:
    message = (text or "").strip()
    if not message.lower().startswith("/tool"):
        return ToolChatResponse(handled=False)

    body = message[5:].strip()
    if not body or body.lower() == "help":
        return ToolChatResponse(handled=True, reply=_help_reply())

    verb, _, rest = body.partition(" ")
    verb = verb.lower().strip()
    rest = rest.strip()

    if verb in {"ls", "list"}:
        return _safe_tool_call(lambda: _list_reply(rest or "."), "I couldn't list that directory.")
    if verb == "search":
        return _safe_tool_call(lambda: _repo_search_reply(rest), "I couldn't search the workspace.")
    if verb == "read":
        return _safe_tool_call(lambda: _read_reply(rest), "I couldn't read that file.")
    if verb in {"write", "append"}:
        return _safe_tool_call(lambda: _write_reply(rest, append=verb == "append"), "I couldn't write that file.")
    if verb == "run":
        return _safe_tool_call(lambda: _run_reply(rest), "I couldn't run that command.")
    if verb == "web":
        return _safe_tool_call(lambda: _web_search_reply(rest), "I couldn't search the web just now.")
    if verb == "google":
        return _safe_tool_call(lambda: _google_search_reply(rest, natural=False), "I couldn't use Google search just now.")
    if verb == "weather":
        return _safe_tool_call(lambda: _weather_reply(rest), "I couldn't check the weather just now.")
    if verb == "calendar":
        if rest.lower() == "auth":
            return _safe_tool_call(lambda: begin_google_calendar_auth(), "I couldn't start Google Calendar authorization.")
        return _safe_tool_call(lambda: _calendar_reply(rest), "I couldn't check your calendar just now.")

    return ToolChatResponse(
        handled=True,
        reply="Unknown `/tool` command. Use `/tool help` to see the available host-side actions.",
    )


def maybe_handle_natural_language_tool_request(text: str) -> ToolChatResponse:
    message = (text or "").strip()
    if not message:
        return ToolChatResponse(handled=False)

    if _CALENDAR_AUTH_RE.search(message):
        return _safe_tool_call(lambda: begin_google_calendar_auth(), "I couldn't start Google Calendar authorization.")

    calendar_match = _CALENDAR_LOOKUP_RE.search(message)
    if calendar_match:
        return _safe_tool_call(lambda: _calendar_reply(message), "I couldn't check your calendar just now.")

    weather_match = _WEATHER_RE.search(message)
    if weather_match:
        location = _clean_query(weather_match.group("location"))
        return _safe_tool_call(lambda: _weather_reply(location), "I couldn't check the weather just now.")

    google_match = _GOOGLE_RE.search(message)
    if google_match:
        query = _clean_query(google_match.group("query"))
        return _safe_tool_call(lambda: _google_search_reply(query, natural=True), "I couldn't search the web just now.")

    web_match = _WEB_SEARCH_RE.search(message)
    if web_match:
        query = _clean_query(web_match.group("query"))
        return _safe_tool_call(lambda: _web_search_reply(query), "I couldn't search the web just now.")

    repo_match = _REPO_SEARCH_RE.search(message)
    if repo_match:
        query = _clean_query(repo_match.group("query"))
        return _safe_tool_call(lambda: _repo_search_reply(query), "I couldn't search the workspace.")

    lower = message.lower()
    if lower.startswith("search the repo for ") or lower.startswith("search the codebase for ") or lower.startswith("search the workspace for "):
        query = _clean_query(message.split(" for ", 1)[1])
        return _safe_tool_call(lambda: _repo_search_reply(query), "I couldn't search the workspace.")
    if lower.startswith("find ") and (" in the repo" in lower or " in the codebase" in lower or " in the workspace" in lower):
        query = _clean_query(re.split(r"\s+in\s+the\s+(?:repo|codebase|workspace)$", message, maxsplit=1, flags=re.IGNORECASE)[0][5:])
        return _safe_tool_call(lambda: _repo_search_reply(query), "I couldn't search the workspace.")

    read_match = _READ_FILE_RE.search(message)
    if read_match:
        return _safe_tool_call(
            lambda: _read_file_reply(
                read_match.group("path"),
                int(read_match.group("start")) if read_match.group("start") else 1,
                int(read_match.group("end")) if read_match.group("end") else None,
            ),
            "I couldn't read that file.",
        )

    list_match = _LIST_DIR_RE.search(message)
    if list_match:
        return _safe_tool_call(lambda: _list_reply(list_match.group("path")), "I couldn't list that directory.")

    run_match = _RUN_RE.search(message)
    if run_match:
        return _safe_tool_call(lambda: _run_reply(run_match.group("command")), "I couldn't run that command.")

    return ToolChatResponse(handled=False)


def _help_reply() -> str:
    manifest = tools.manifest()
    commands = "\n".join(f"- `{item}`" for item in manifest["commands"])
    allowed = "\n".join(f"- `{item}`" for item in manifest["allowed_commands"])
    return (
        "Local agent tools are available on this host.\n\n"
        f"{commands}\n\n"
        "Allowed commands:\n"
        f"{allowed}"
    )


def _safe_tool_call(fn: Callable[[], str], fallback: str) -> ToolChatResponse:
    try:
        return ToolChatResponse(handled=True, reply=fn())
    except Exception as exc:
        detail = str(exc).strip()
        if detail:
            return ToolChatResponse(handled=True, reply=f"{fallback} {detail}")
        return ToolChatResponse(handled=True, reply=fallback)


def _list_reply(path: str) -> str:
    entries = tools.list_directory(path or ".")
    view_path = path or "."
    return f"Directory listing for `{view_path}`:\n" + ("\n".join(f"- `{item}`" for item in entries) or "- `(empty)`")


def _repo_search_reply(query: str) -> str:
    result = tools.search_workspace(query)
    if not result.matches:
        return f"No matches found for `{result.query}` in the workspace."
    lines = [f"- `{match.path}:{match.line}` {match.text}" for match in result.matches]
    if result.truncated:
        lines.append("- `...` more matches were omitted.")
    return f"Search results for `{result.query}`:\n" + "\n".join(lines)


def _read_reply(rest: str) -> str:
    read_path, start_line, end_line = _parse_read_args(rest)
    return _read_file_reply(read_path, start_line, end_line)


def _read_file_reply(path: str, start_line: int = 1, end_line: int | None = None) -> str:
    result = tools.read_file(path, start_line=start_line, end_line=end_line)
    suffix = "\n\n`...` more lines were omitted." if result.truncated else ""
    return f"Contents of `{result.path}` (lines {result.start_line}-{result.end_line}):\n```text\n{result.text}\n```{suffix}"


def _write_reply(rest: str, *, append: bool) -> str:
    path, content = _parse_write_args(rest)
    result = tools.write_file(path, content, append=append)
    action = "Appended to" if result.append else "Wrote"
    return f"{action} `{result.path}` ({result.bytes_written} bytes)."


def _run_reply(command: str) -> str:
    result = tools.run_safe_command(command)
    chunks = [f"Command `{result.command}` exited with `{result.returncode}`."]
    if result.timed_out:
        chunks.append("The command timed out.")
    if result.stdout:
        chunks.append(f"Stdout:\n```text\n{result.stdout}\n```")
    if result.stderr:
        chunks.append(f"Stderr:\n```text\n{result.stderr}\n```")
    return "\n\n".join(chunks)


def _web_search_reply(query: str) -> str:
    result = search_web(query)
    lines = [
        f"- [{item.title}]({item.url})" + (f" — {item.snippet}" if item.snippet else "")
        for item in result.items
    ]
    return f"Web results from `{result.provider}` for `{result.query}`:\n" + "\n".join(lines)


def _google_search_reply(query: str, *, natural: bool) -> str:
    provider = str(cfg.settings.agent_web_search_provider or "").strip().lower()
    if provider != "google_cse":
        if natural:
            result = search_web(query)
            note = (
                "Google search is not configured on this host, so I used the current web search provider instead.\n\n"
                if not google_search_is_configured()
                else "Google search is not the active provider on this host, so I used the current web search provider instead.\n\n"
            )
            lines = [
                f"- [{item.title}]({item.url})" + (f" — {item.snippet}" if item.snippet else "")
                for item in result.items
            ]
            return note + f"Web results from `{result.provider}` for `{result.query}`:\n" + "\n".join(lines)
        return (
            "Google search is not the active provider on this host. "
            "Set `JARVIN_AGENT_WEB_SEARCH_PROVIDER=google_cse` with valid Google search credentials, "
            "or use `/tool web <query>` for the current web-search provider."
        )

    result = search_web(query)
    lines = [
        f"- [{item.title}]({item.url})" + (f" — {item.snippet}" if item.snippet else "")
        for item in result.items
    ]
    return f"Google results for `{result.query}`:\n" + "\n".join(lines)


def _weather_reply(location: str) -> str:
    result = get_weather(location)
    return (
        f"Weather for `{result.location_label}`:\n"
        f"- Current: {result.forecast_summary}\n"
        f"- Temperature: {result.temperature}\n"
        f"- Feels like: {result.feels_like}\n"
        f"- Wind: {result.wind}\n"
        f"- Outlook: {result.daily_outlook}"
    )


def _calendar_reply(raw: str) -> str:
    if not google_calendar_credentials_configured():
        creds_path = cfg.settings.google_calendar_credentials_file
        return (
            "I can't access your Google Calendar yet because this host does not have Google OAuth credentials configured. "
            f"Put your desktop OAuth client JSON at `{creds_path}`, then ask me to connect your calendar."
        )

    if not google_calendar_token_available():
        return (
            "I can access your Google Calendar once you authorize it on this host. "
            "Ask me to connect or authorize your Google Calendar and I will start the OAuth flow."
        )

    window_days = _infer_calendar_window_days(raw)
    agenda = get_calendar_agenda(window_days=window_days)
    if not agenda.events:
        return f"No events were found in `{agenda.calendar_id}` for the next {agenda.window_days} day(s)."
    lines = [
        f"- `{event.starts_at}` {event.title}" + (f" — {event.location}" if event.location else "")
        for event in agenda.events
    ]
    return f"Upcoming events from `{agenda.calendar_id}` for the next {agenda.window_days} day(s):\n" + "\n".join(lines)


def _infer_calendar_window_days(text: str) -> int:
    lower = text.lower()
    stripped = lower.strip()
    if stripped.isdigit():
        return max(1, int(stripped))
    if "today" in lower:
        return 1
    if "tomorrow" in lower:
        return 2
    if "next week" in lower or "this week" in lower:
        return 7
    days_match = re.search(r"next\s+(\d+)\s+days?", lower)
    if days_match:
        return max(1, int(days_match.group(1)))
    return 7


def _parse_read_args(rest: str) -> tuple[str, int, int | None]:
    parts = rest.split()
    if not parts:
        raise ValueError("Usage: /tool read <path> [start_line] [end_line]")
    path = parts[0]
    start = int(parts[1]) if len(parts) >= 2 else 1
    end = int(parts[2]) if len(parts) >= 3 else None
    return path, start, end


def _parse_write_args(rest: str) -> tuple[str, str]:
    path, separator, content = rest.partition("\n")
    if not path.strip():
        raise ValueError("Usage: /tool write <path> then put file contents on the next lines")
    if not separator:
        raise ValueError("Put the file contents on the lines after `/tool write <path>`.")
    return path.strip(), content


def _clean_query(value: str) -> str:
    return str(value or "").strip().rstrip("?.!,")
