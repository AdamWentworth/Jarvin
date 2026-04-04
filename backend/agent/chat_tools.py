from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

import config as cfg
from backend.agent import tools
from backend.agent.external_tools import (
    begin_google_calendar_auth,
    create_calendar_event_from_text,
    delete_calendar_event,
    find_calendar_events,
    get_calendar_agenda,
    get_calendar_event_details,
    get_weather,
    google_calendar_credentials_configured,
    google_calendar_token_available,
    google_search_is_configured,
    prepare_reschedule_times,
    reschedule_calendar_event,
    search_web,
    update_calendar_event_fields,
)
from backend.agent.pending_actions import (
    PendingCalendarAction,
    clear_pending_calendar_action,
    get_pending_calendar_action,
    set_pending_calendar_action,
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
_CALENDAR_DETAILS_RE = re.compile(
    r"(?:(?:show|read|open|view)\s+(?:me\s+)?(?:event(?:\s+details)?|details(?:\s+for)?)\s+)(?P<query>.+?)(?:\s+(?:on|in)\s+(?:my\s+)?calendar)?$",
    re.IGNORECASE,
)
_CALENDAR_DELETE_RE = re.compile(
    r"(?:(?:please\s+)?(?:delete|remove|cancel)\s+)(?P<query>.+?)(?:\s+(?:from|on)\s+(?:my\s+)?calendar)?$",
    re.IGNORECASE,
)
_CALENDAR_RENAME_RE = re.compile(
    r"(?:(?:please\s+)?(?:rename|retitle)\s+)(?P<query>.+?)\s+(?:to|as)\s+(?P<new_title>.+?)(?:\s+(?:on|in)\s+(?:my\s+)?calendar)?$",
    re.IGNORECASE,
)
_CALENDAR_TITLE_RE = re.compile(
    r"(?:(?:please\s+)?(?:set|change|update)\s+(?:the\s+)?title\s+(?:of|for)\s+)(?P<query>.+?)\s+to\s+(?P<new_title>.+?)(?:\s+(?:on|in)\s+(?:my\s+)?calendar)?$",
    re.IGNORECASE,
)
_CALENDAR_LOCATION_RE = re.compile(
    r"(?:(?:please\s+)?(?:set|change|update)\s+(?:the\s+)?location\s+(?:of|for)\s+)(?P<query>.+?)\s+to\s+(?P<location>.+?)(?:\s+(?:on|in)\s+(?:my\s+)?calendar)?$",
    re.IGNORECASE,
)
_CALENDAR_CLEAR_LOCATION_RE = re.compile(
    r"(?:(?:please\s+)?(?:clear|remove|delete)\s+(?:the\s+)?location\s+(?:of|from)\s+)(?P<query>.+?)(?:\s+(?:on|in)\s+(?:my\s+)?calendar)?$",
    re.IGNORECASE,
)
_CALENDAR_NOTES_RE = re.compile(
    r"(?:(?:please\s+)?(?:set|change|update)\s+(?:the\s+)?(?:notes|description)\s+(?:of|for)\s+)(?P<query>.+?)\s+to\s+(?P<description>.+?)(?:\s+(?:on|in)\s+(?:my\s+)?calendar)?$",
    re.IGNORECASE,
)
_CALENDAR_CLEAR_NOTES_RE = re.compile(
    r"(?:(?:please\s+)?(?:clear|remove|delete)\s+(?:the\s+)?(?:notes|description)\s+(?:of|from)\s+)(?P<query>.+?)(?:\s+(?:on|in)\s+(?:my\s+)?calendar)?$",
    re.IGNORECASE,
)
_CALENDAR_MOVE_RE = re.compile(
    r"(?:(?:please\s+)?(?:move|reschedule|change|update)\s+)(?P<query>.+?)\s+to\s+(?P<when>.+?)(?:\s+(?:on|in)\s+(?:my\s+)?calendar)?$",
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

_CONFIRM_PATTERNS = {
    "yes",
    "y",
    "confirm",
    "go ahead",
    "do it",
    "please do",
    "okay",
    "ok",
    "sure",
}
_CANCEL_PATTERNS = {
    "no",
    "n",
    "cancel",
    "stop",
    "never mind",
    "nevermind",
}


@dataclass(frozen=True)
class ToolChatResponse:
    handled: bool
    reply: str = ""


def maybe_handle_assistant_tool_request(text: str, *, conversation_id: int | None = None) -> ToolChatResponse:
    pending = _maybe_handle_pending_confirmation(text, conversation_id=conversation_id)
    if pending.handled:
        return pending

    explicit = maybe_handle_tool_command(text, conversation_id=conversation_id)
    if explicit.handled:
        return explicit

    return maybe_handle_natural_language_tool_request(text, conversation_id=conversation_id)


def maybe_handle_tool_command(text: str, *, conversation_id: int | None = None) -> ToolChatResponse:
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
        return _safe_tool_call(
            lambda: _calendar_command_reply(rest, conversation_id=conversation_id),
            "I couldn't work with your calendar just now.",
        )

    return ToolChatResponse(
        handled=True,
        reply="Unknown `/tool` command. Use `/tool help` to see the available host-side actions.",
    )


def maybe_handle_natural_language_tool_request(text: str, *, conversation_id: int | None = None) -> ToolChatResponse:
    message = (text or "").strip()
    if not message:
        return ToolChatResponse(handled=False)

    if _CALENDAR_AUTH_RE.search(message):
        return _safe_tool_call(lambda: begin_google_calendar_auth(), "I couldn't start Google Calendar authorization.")

    details_match = _CALENDAR_DETAILS_RE.search(message)
    if details_match:
        query = _clean_query(details_match.group("query"))
        return _safe_tool_call(lambda: _calendar_details_reply(query), "I couldn't open that calendar event.")

    calendar_create = _extract_calendar_create_text(message)
    if calendar_create:
        return _safe_tool_call(lambda: _calendar_create_reply(calendar_create), "I couldn't create that calendar event.")

    rename_match = _CALENDAR_RENAME_RE.search(message) or _CALENDAR_TITLE_RE.search(message)
    if rename_match:
        query = _clean_query(rename_match.group("query"))
        new_title = _clean_query(rename_match.group("new_title"))
        return _safe_tool_call(
            lambda: _calendar_update_request_reply(query, conversation_id=conversation_id, title=new_title),
            "I couldn't prepare that calendar title change.",
        )

    location_match = _CALENDAR_LOCATION_RE.search(message)
    if location_match:
        query = _clean_query(location_match.group("query"))
        location = location_match.group("location").strip()
        return _safe_tool_call(
            lambda: _calendar_update_request_reply(query, conversation_id=conversation_id, location=location),
            "I couldn't prepare that calendar location change.",
        )

    clear_location_match = _CALENDAR_CLEAR_LOCATION_RE.search(message)
    if clear_location_match:
        query = _clean_query(clear_location_match.group("query"))
        return _safe_tool_call(
            lambda: _calendar_update_request_reply(query, conversation_id=conversation_id, location=""),
            "I couldn't prepare that calendar location update.",
        )

    notes_match = _CALENDAR_NOTES_RE.search(message)
    if notes_match:
        query = _clean_query(notes_match.group("query"))
        description = notes_match.group("description").strip()
        return _safe_tool_call(
            lambda: _calendar_update_request_reply(query, conversation_id=conversation_id, description=description),
            "I couldn't prepare that calendar notes update.",
        )

    clear_notes_match = _CALENDAR_CLEAR_NOTES_RE.search(message)
    if clear_notes_match:
        query = _clean_query(clear_notes_match.group("query"))
        return _safe_tool_call(
            lambda: _calendar_update_request_reply(query, conversation_id=conversation_id, description=""),
            "I couldn't prepare that calendar notes update.",
        )

    delete_match = _CALENDAR_DELETE_RE.search(message)
    if delete_match:
        query = _clean_query(delete_match.group("query"))
        return _safe_tool_call(
            lambda: _calendar_delete_request_reply(query, conversation_id=conversation_id),
            "I couldn't prepare that calendar deletion.",
        )

    move_match = _CALENDAR_MOVE_RE.search(message)
    if move_match:
        query = _clean_query(move_match.group("query"))
        when_text = _clean_query(move_match.group("when"))
        return _safe_tool_call(
            lambda: _calendar_move_request_reply(query, when_text, conversation_id=conversation_id),
            "I couldn't prepare that calendar update.",
        )

    if _CALENDAR_LOOKUP_RE.search(message):
        return _safe_tool_call(lambda: _calendar_lookup_reply(message), "I couldn't check your calendar just now.")

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


def _maybe_handle_pending_confirmation(text: str, *, conversation_id: int | None) -> ToolChatResponse:
    pending = get_pending_calendar_action(conversation_id)
    if pending is None:
        return ToolChatResponse(handled=False)

    normalized = _normalize_confirmation_text(text)
    if normalized in _CANCEL_PATTERNS:
        clear_pending_calendar_action(conversation_id)
        return ToolChatResponse(handled=True, reply="Okay, I canceled that pending calendar change.")

    if normalized not in _CONFIRM_PATTERNS:
        return ToolChatResponse(handled=False)

    clear_pending_calendar_action(conversation_id)
    if pending.action == "calendar_delete":
        deleted = delete_calendar_event(pending.event_id)
        return ToolChatResponse(
            handled=True,
            reply=f"Deleted `{deleted.title}` from your calendar. It was scheduled for `{deleted.starts_at}`.",
        )

    if pending.action == "calendar_reschedule":
        if not pending.new_start_iso or not pending.new_end_iso:
            raise ValueError("That pending calendar update is missing the new time details.")
        updated = reschedule_calendar_event(
            pending.event_id,
            new_start_iso=pending.new_start_iso,
            new_end_iso=pending.new_end_iso,
        )
        return ToolChatResponse(
            handled=True,
            reply=f"Rescheduled `{updated.title}`. It is now set for `{updated.starts_at}`.",
        )

    if pending.action == "calendar_update_fields":
        updated = update_calendar_event_fields(
            pending.event_id,
            title=pending.new_title,
            location=pending.new_location,
            description=pending.new_description,
        )
        return ToolChatResponse(
            handled=True,
            reply=_calendar_field_update_success_reply(updated, pending),
        )

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


def _calendar_command_reply(rest: str, *, conversation_id: int | None) -> str:
    lower = rest.lower()
    if lower == "auth":
        return begin_google_calendar_auth()
    if lower.startswith("details ") or lower.startswith("show "):
        query = rest.split(" ", 1)[1].strip()
        return _calendar_details_reply(query)
    if lower.startswith("add ") or lower.startswith("create "):
        details = rest.split(" ", 1)[1].strip()
        return _calendar_create_reply(details)
    if lower.startswith("rename ") or lower.startswith("retitle "):
        _, _, payload = rest.partition(" ")
        query, new_title = _partition_calendar_payload(payload, "Use `/tool calendar rename <event name> | <new title>`.") 
        return _calendar_update_request_reply(query, conversation_id=conversation_id, title=new_title)
    if lower.startswith("title "):
        _, _, payload = rest.partition(" ")
        query, new_title = _partition_calendar_payload(payload, "Use `/tool calendar title <event name> | <new title>`.") 
        return _calendar_update_request_reply(query, conversation_id=conversation_id, title=new_title)
    if lower.startswith("location "):
        _, _, payload = rest.partition(" ")
        query, location = _partition_calendar_payload(payload, "Use `/tool calendar location <event name> | <new location>`.") 
        return _calendar_update_request_reply(query, conversation_id=conversation_id, location=location)
    if lower.startswith("clear-location "):
        query = rest.split(" ", 1)[1].strip()
        return _calendar_update_request_reply(query, conversation_id=conversation_id, location="")
    if lower.startswith("notes ") or lower.startswith("description "):
        _, _, payload = rest.partition(" ")
        query, description = _partition_calendar_payload(payload, "Use `/tool calendar notes <event name> | <new notes>`.") 
        return _calendar_update_request_reply(query, conversation_id=conversation_id, description=description)
    if lower.startswith("clear-notes ") or lower.startswith("clear-description "):
        query = rest.split(" ", 1)[1].strip()
        return _calendar_update_request_reply(query, conversation_id=conversation_id, description="")
    if lower.startswith("delete ") or lower.startswith("remove ") or lower.startswith("cancel "):
        query = rest.split(" ", 1)[1].strip()
        return _calendar_delete_request_reply(query, conversation_id=conversation_id)
    if lower.startswith("move ") or lower.startswith("reschedule ") or lower.startswith("update "):
        _, _, payload = rest.partition(" ")
        query, sep, when_text = payload.partition("|")
        if not sep:
            move_match = _CALENDAR_MOVE_RE.search(payload)
            if move_match:
                query = move_match.group("query")
                when_text = move_match.group("when")
        query = _clean_query(query)
        when_text = _clean_query(when_text)
        if not query or not when_text:
            raise ValueError("Use `/tool calendar move <event name> | <new date/time>`.")
        return _calendar_move_request_reply(query, when_text, conversation_id=conversation_id)
    return _calendar_lookup_reply(rest)


def _calendar_create_reply(details: str) -> str:
    created = create_calendar_event_from_text(details)
    location = f" at {created.location}" if created.location else ""
    return f"Created `{created.title}` on your calendar for `{created.starts_at}`{location}."


def _calendar_details_reply(query: str) -> str:
    matches = find_calendar_events(query)
    match = _pick_single_calendar_match(matches, query)
    details = get_calendar_event_details(match.event_id)
    notes = details.description.strip() or "(none)"
    location = details.location.strip() or "(none)"
    return (
        f"Details for `{details.title}`:\n"
        f"- Starts: `{details.starts_at}`\n"
        f"- Ends: `{details.ends_at}`\n"
        f"- Location: `{location}`\n"
        f"- Notes: {notes}"
    )


def _calendar_delete_request_reply(query: str, *, conversation_id: int | None) -> str:
    matches = find_calendar_events(query)
    match = _pick_single_calendar_match(matches, query)
    set_pending_calendar_action(
        conversation_id,
        PendingCalendarAction(
            action="calendar_delete",
            event_id=match.event_id,
            title=match.title,
            starts_at=_display_event_time(match),
        ),
    )
    return (
        f"I found `{match.title}` scheduled for `{_display_event_time(match)}`. "
        "Reply `yes` to confirm deleting it, or `cancel` to keep it."
    )


def _calendar_move_request_reply(query: str, when_text: str, *, conversation_id: int | None) -> str:
    matches = find_calendar_events(query)
    match = _pick_single_calendar_match(matches, query)
    new_start_iso, new_end_iso = prepare_reschedule_times(match, when_text)
    preview = _format_iso_for_display(new_start_iso)
    set_pending_calendar_action(
        conversation_id,
        PendingCalendarAction(
            action="calendar_reschedule",
            event_id=match.event_id,
            title=match.title,
            starts_at=_display_event_time(match),
            new_start_iso=new_start_iso,
            new_end_iso=new_end_iso,
        ),
    )
    return (
        f"I found `{match.title}` scheduled for `{_display_event_time(match)}`. "
        f"Reply `yes` to move it to `{preview}`, or `cancel` to leave it alone."
    )


def _calendar_update_request_reply(
    query: str,
    *,
    conversation_id: int | None,
    title: str | None = None,
    location: str | None = None,
    description: str | None = None,
) -> str:
    matches = find_calendar_events(query)
    match = _pick_single_calendar_match(matches, query)
    set_pending_calendar_action(
        conversation_id,
        PendingCalendarAction(
            action="calendar_update_fields",
            event_id=match.event_id,
            title=match.title,
            starts_at=_display_event_time(match),
            new_title=title,
            new_location=location,
            new_description=description,
        ),
    )
    return (
        f"I found `{match.title}` scheduled for `{_display_event_time(match)}`. "
        f"Reply `yes` to apply this update: {_describe_calendar_field_update(title=title, location=location, description=description)}, "
        "or `cancel` to leave it alone."
    )


def _calendar_lookup_reply(raw: str) -> str:
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
        f"- `{event.starts_at}` {event.title}" + (f" at {event.location}" if event.location else "")
        for event in agenda.events
    ]
    return f"Upcoming events from `{agenda.calendar_id}` for the next {agenda.window_days} day(s):\n" + "\n".join(lines)


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


def _pick_single_calendar_match(matches: list, query: str):
    if not matches:
        raise ValueError(f"I couldn't find a calendar event matching '{query}'.")
    if len(matches) > 1:
        lines = [f"- `{_display_event_time(item)}` {item.title}" for item in matches[:5]]
        raise ValueError(
            "I found multiple matching events. Please be more specific:\n" + "\n".join(lines)
        )
    return matches[0]


def _calendar_field_update_success_reply(updated, pending: PendingCalendarAction) -> str:
    bits = [f"Updated `{updated.title}` on your calendar."]
    bits.append(f"It now starts at `{updated.starts_at}` and ends at `{updated.ends_at}`.")
    if pending.new_title is not None:
        bits.append(f"Title: `{updated.title}`.")
    if pending.new_location is not None:
        if updated.location:
            bits.append(f"Location: `{updated.location}`.")
        else:
            bits.append("Location cleared.")
    elif updated.location:
        bits.append(f"Location: `{updated.location}`.")
    if pending.new_description is not None:
        if updated.description:
            bits.append(f"Notes: {updated.description}")
        else:
            bits.append("Notes cleared.")
    elif updated.description:
        bits.append(f"Notes: {updated.description}")
    return " ".join(bits)


def _describe_calendar_field_update(
    *,
    title: str | None = None,
    location: str | None = None,
    description: str | None = None,
) -> str:
    changes: list[str] = []
    if title is not None:
        changes.append(f"title -> `{title}`")
    if location is not None:
        changes.append("location cleared" if location == "" else f"location -> `{location}`")
    if description is not None:
        changes.append("notes cleared" if description == "" else f"notes updated")
    return ", ".join(changes) or "no visible changes"


def _display_event_time(event) -> str:
    return _format_iso_for_display(event.starts_at)


def _format_iso_for_display(value: str) -> str:
    raw = str(value or "").strip()
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return raw
    if parsed.tzinfo is None:
        return parsed.strftime("%Y-%m-%d")
    return parsed.astimezone().strftime("%Y-%m-%d %I:%M %p")


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


def _partition_calendar_payload(payload: str, usage: str) -> tuple[str, str]:
    query, sep, value = payload.partition("|")
    query = _clean_query(query)
    value = value.strip()
    if not sep or not query or not value:
        raise ValueError(usage)
    return query, value


def _extract_calendar_create_text(message: str) -> str | None:
    lower = message.lower()
    if "calendar" not in lower:
        return None
    if not any(lower.startswith(prefix) for prefix in ("add ", "create ", "schedule ", "put ", "please add ", "please create ", "please schedule ", "please put ")):
        return None

    candidate = re.sub(r"^(?:please\s+)?(?:add|create|schedule|put)\s+", "", message, flags=re.IGNORECASE)
    candidate = re.sub(r"\s+(?:to|on|in)\s+(?:my\s+)?calendar\b", "", candidate, flags=re.IGNORECASE).strip()
    cleaned = _clean_query(candidate)
    return cleaned or None


def _normalize_confirmation_text(text: str) -> str:
    return str(text or "").strip().lower().rstrip(".!")


def _clean_query(value: str) -> str:
    return str(value or "").strip().rstrip("?.!,")
