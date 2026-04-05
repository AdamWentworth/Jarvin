from __future__ import annotations

import re
from datetime import datetime

import config as cfg
import backend.agent.host_tool_runtime as host_tool_runtime
from backend.agent.chat.chat_intent_patterns import CALENDAR_MOVE_RE
from backend.agent.integration_facade import (
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
    update_calendar_event_fields,
    browse_search_results,
)
from backend.agent.calendar_pending_actions import PendingCalendarAction, set_pending_calendar_action
from backend.ai_engine import build_jarvin_config, generate_reply


def calendar_command_reply(rest: str, *, conversation_id: int | None) -> str:
    lower = rest.lower()
    if lower == "auth":
        from backend.agent.integration_facade import begin_google_calendar_auth

        return begin_google_calendar_auth()
    if lower.startswith("details ") or lower.startswith("show "):
        query = rest.split(" ", 1)[1].strip()
        return calendar_details_reply(query)
    if lower.startswith("add ") or lower.startswith("create "):
        details = rest.split(" ", 1)[1].strip()
        return calendar_create_reply(details)
    if lower.startswith("rename ") or lower.startswith("retitle "):
        _, _, payload = rest.partition(" ")
        query, new_title = partition_calendar_payload(payload, "Use `/tool calendar rename <event name> | <new title>`.")
        return calendar_update_request_reply(query, conversation_id=conversation_id, title=new_title)
    if lower.startswith("title "):
        _, _, payload = rest.partition(" ")
        query, new_title = partition_calendar_payload(payload, "Use `/tool calendar title <event name> | <new title>`.")
        return calendar_update_request_reply(query, conversation_id=conversation_id, title=new_title)
    if lower.startswith("location "):
        _, _, payload = rest.partition(" ")
        query, location = partition_calendar_payload(payload, "Use `/tool calendar location <event name> | <new location>`.")
        return calendar_update_request_reply(query, conversation_id=conversation_id, location=location)
    if lower.startswith("clear-location "):
        query = rest.split(" ", 1)[1].strip()
        return calendar_update_request_reply(query, conversation_id=conversation_id, location="")
    if lower.startswith("notes ") or lower.startswith("description "):
        _, _, payload = rest.partition(" ")
        query, description = partition_calendar_payload(payload, "Use `/tool calendar notes <event name> | <new notes>`.")
        return calendar_update_request_reply(query, conversation_id=conversation_id, description=description)
    if lower.startswith("clear-notes ") or lower.startswith("clear-description "):
        query = rest.split(" ", 1)[1].strip()
        return calendar_update_request_reply(query, conversation_id=conversation_id, description="")
    if lower.startswith("delete ") or lower.startswith("remove ") or lower.startswith("cancel "):
        query = rest.split(" ", 1)[1].strip()
        return calendar_delete_request_reply(query, conversation_id=conversation_id)
    if lower.startswith("move ") or lower.startswith("reschedule ") or lower.startswith("update "):
        _, _, payload = rest.partition(" ")
        query, sep, when_text = payload.partition("|")
        if not sep:
            move_match = CALENDAR_MOVE_RE.search(payload)
            if move_match:
                query = move_match.group("query")
                when_text = move_match.group("when")
        query = clean_query(query)
        when_text = clean_query(when_text)
        if not query or not when_text:
            raise ValueError("Use `/tool calendar move <event name> | <new date/time>`.")
        return calendar_move_request_reply(query, when_text, conversation_id=conversation_id)
    return calendar_lookup_reply(rest)


def calendar_create_reply(details: str) -> str:
    created = create_calendar_event_from_text(details)
    location = f" at {created.location}" if created.location else ""
    return f"Created `{created.title}` on your calendar for `{created.starts_at}`{location}."


def calendar_details_reply(query: str) -> str:
    matches = find_calendar_events(query)
    match = pick_single_calendar_match(matches, query)
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


def calendar_delete_request_reply(query: str, *, conversation_id: int | None) -> str:
    matches = find_calendar_events(query)
    match = pick_single_calendar_match(matches, query)
    set_pending_calendar_action(
        conversation_id,
        PendingCalendarAction(
            action="calendar_delete",
            event_id=match.event_id,
            title=match.title,
            starts_at=display_event_time(match),
        ),
    )
    return (
        f"I found `{match.title}` scheduled for `{display_event_time(match)}`. "
        "Reply `yes` to confirm deleting it, or `cancel` to keep it."
    )


def calendar_move_request_reply(query: str, when_text: str, *, conversation_id: int | None) -> str:
    matches = find_calendar_events(query)
    match = pick_single_calendar_match(matches, query)
    new_start_iso, new_end_iso = prepare_reschedule_times(match, when_text)
    preview = format_iso_for_display(new_start_iso)
    set_pending_calendar_action(
        conversation_id,
        PendingCalendarAction(
            action="calendar_reschedule",
            event_id=match.event_id,
            title=match.title,
            starts_at=display_event_time(match),
            new_start_iso=new_start_iso,
            new_end_iso=new_end_iso,
        ),
    )
    return (
        f"I found `{match.title}` scheduled for `{display_event_time(match)}`. "
        f"Reply `yes` to move it to `{preview}`, or `cancel` to leave it alone."
    )


def calendar_update_request_reply(
    query: str,
    *,
    conversation_id: int | None,
    title: str | None = None,
    location: str | None = None,
    description: str | None = None,
) -> str:
    matches = find_calendar_events(query)
    match = pick_single_calendar_match(matches, query)
    set_pending_calendar_action(
        conversation_id,
        PendingCalendarAction(
            action="calendar_update_fields",
            event_id=match.event_id,
            title=match.title,
            starts_at=display_event_time(match),
            new_title=title,
            new_location=location,
            new_description=description,
        ),
    )
    return (
        f"I found `{match.title}` scheduled for `{display_event_time(match)}`. "
        f"Reply `yes` to apply this update: {describe_calendar_field_update(title=title, location=location, description=description)}, "
        "or `cancel` to leave it alone."
    )


def calendar_lookup_reply(raw: str, *, window_days_override: int | None = None) -> str:
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

    inferred_window_days = infer_calendar_window_days(raw)
    window_days = int(window_days_override if window_days_override is not None else (inferred_window_days or 7))
    agenda = get_calendar_agenda(window_days=window_days)
    if not agenda.events:
        return f"No events were found in `{agenda.calendar_id}` for the next {agenda.window_days} day(s)."
    lines = [
        f"- `{event.starts_at}` {event.title}" + (f" at {event.location}" if event.location else "")
        for event in agenda.events
    ]
    return f"Upcoming events from `{agenda.calendar_id}` for the next {agenda.window_days} day(s):\n" + "\n".join(lines)


def list_reply(path: str) -> str:
    entries = host_tool_runtime.list_directory(path or ".")
    view_path = path or "."
    return f"Directory listing for `{view_path}`:\n" + ("\n".join(f"- `{item}`" for item in entries) or "- `(empty)`")


def repo_search_reply(query: str) -> str:
    result = host_tool_runtime.search_workspace(query)
    if not result.matches:
        return f"No matches found for `{result.query}` in the workspace."
    lines = [f"- `{match.path}:{match.line}` {match.text}" for match in result.matches]
    if result.truncated:
        lines.append("- `...` more matches were omitted.")
    return f"Search results for `{result.query}`:\n" + "\n".join(lines)


def read_reply(rest: str) -> str:
    read_path, start_line, end_line = parse_read_args(rest)
    return read_file_reply(read_path, start_line, end_line)


def read_file_reply(path: str, start_line: int = 1, end_line: int | None = None) -> str:
    result = host_tool_runtime.read_file(path, start_line=start_line, end_line=end_line)
    suffix = "\n\n`...` more lines were omitted." if result.truncated else ""
    return f"Contents of `{result.path}` (lines {result.start_line}-{result.end_line}):\n```text\n{result.text}\n```{suffix}"


def write_reply(rest: str, *, append: bool) -> str:
    path, content = parse_write_args(rest)
    result = host_tool_runtime.write_file(path, content, append=append)
    action = "Appended to" if result.append else "Wrote"
    return f"{action} `{result.path}` ({result.bytes_written} bytes)."


def run_reply(command: str) -> str:
    result = host_tool_runtime.run_safe_command(command)
    chunks = [f"Command `{result.command}` exited with `{result.returncode}`."]
    if result.timed_out:
        chunks.append("The command timed out.")
    if result.stdout:
        chunks.append(f"Stdout:\n```text\n{result.stdout}\n```")
    if result.stderr:
        chunks.append(f"Stderr:\n```text\n{result.stderr}\n```")
    return "\n\n".join(chunks)


def web_search_reply(query: str) -> str:
    research = browse_search_results(query)
    return render_web_research_reply(research, label="Web")


def google_search_reply(query: str, *, natural: bool) -> str:
    provider = str(cfg.settings.agent_web_search_provider or "").strip().lower()
    if provider != "google_cse":
        if natural:
            research = browse_search_results(query)
            note = (
                "Google search is not configured on this host, so I used the current web search provider instead.\n\n"
                if not google_search_is_configured()
                else "Google search is not the active provider on this host, so I used the current web search provider instead.\n\n"
            )
            return note + render_web_research_reply(research, label="Web")
        return (
            "Google search is not the active provider on this host. "
            "Set `JARVIN_AGENT_WEB_SEARCH_PROVIDER=google_cse` with valid Google search credentials, "
            "or use `/tool web <query>` for the current web-search provider."
        )

    research = browse_search_results(query)
    return render_web_research_reply(research, label="Google")


def render_web_research_reply(research, *, label: str) -> str:
    if getattr(research, "pages", None):
        summary = summarize_web_research(research)
        if not summary:
            summary = fallback_web_research_summary(research)
        sources = "\n".join(
            f"- [{page.title}]({page.url})"
            for page in research.pages
        )
        return (
            f"{label} search from `{research.provider}` for `{research.query}`:\n\n"
            f"{summary}\n\n"
            f"Sources:\n{sources}"
        )

    lines = [
        f"- [{item.title}]({item.url})" + (f" - {item.snippet}" if item.snippet else "")
        for item in research.items
    ]
    return f"{label} results from `{research.provider}` for `{research.query}`:\n" + "\n".join(lines)


def summarize_web_research(research) -> str:
    source_blocks = []
    for index, page in enumerate(research.pages, start=1):
        source_blocks.append(
            f"[{index}] {page.title}\n"
            f"URL: {page.url}\n"
            f"Excerpt:\n{page.excerpt}"
        )

    system = (
        "You are summarizing web research for Jarvin. "
        "Write 2-4 concise bullet points that answer the user's search request from the provided sources. "
        "Cite supporting source numbers inline like [1] or [2]. "
        "If the sources are thin or uncertain, say so briefly."
    )
    cfg_obj = build_jarvin_config(
        mode="agent_strong",
        system_instructions=system,
        temperature=0.2,
        max_tokens=320,
    )
    prompt = (
        f"Search query: {research.query}\n"
        "Answer from the source notes below. Prefer direct usefulness over verbosity."
    )
    return generate_reply(prompt, cfg=cfg_obj, context="\n\n".join(source_blocks)).strip()


def fallback_web_research_summary(research) -> str:
    bullets = []
    for index, page in enumerate(research.pages, start=1):
        first_line = page.excerpt.splitlines()[0].strip() if page.excerpt else ""
        snippet = first_line[:220].rstrip()
        bullets.append(f"- [{index}] {page.title}: {snippet}")
    return "\n".join(bullets)


def weather_reply(location: str) -> str:
    result = get_weather(location)
    return (
        f"Weather for `{result.location_label}`:\n"
        f"- Current: {result.forecast_summary}\n"
        f"- Temperature: {result.temperature}\n"
        f"- Feels like: {result.feels_like}\n"
        f"- Wind: {result.wind}\n"
        f"- Outlook: {result.daily_outlook}"
    )


def pick_single_calendar_match(matches: list, query: str):
    if not matches:
        raise ValueError(f"I couldn't find a calendar event matching '{query}'.")
    if len(matches) > 1:
        lines = [f"- `{display_event_time(item)}` {item.title}" for item in matches[:5]]
        raise ValueError(
            "I found multiple matching events. Please be more specific:\n" + "\n".join(lines)
        )
    return matches[0]


def calendar_field_update_success_reply(updated, pending: PendingCalendarAction) -> str:
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


def describe_calendar_field_update(
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
        changes.append("notes cleared" if description == "" else "notes updated")
    return ", ".join(changes) or "no visible changes"


def display_event_time(event) -> str:
    return format_iso_for_display(event.starts_at)


def format_iso_for_display(value: str) -> str:
    raw = str(value or "").strip()
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return raw
    if parsed.tzinfo is None:
        return parsed.strftime("%Y-%m-%d")
    return parsed.astimezone().strftime("%Y-%m-%d %I:%M %p")


def infer_calendar_window_days(text: str) -> int | None:
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
    return None


def parse_read_args(rest: str) -> tuple[str, int, int | None]:
    parts = rest.split()
    if not parts:
        raise ValueError("Usage: /tool read <path> [start_line] [end_line]")
    path = parts[0]
    start = int(parts[1]) if len(parts) >= 2 else 1
    end = int(parts[2]) if len(parts) >= 3 else None
    return path, start, end


def parse_write_args(rest: str) -> tuple[str, str]:
    path, separator, content = rest.partition("\n")
    if not path.strip():
        raise ValueError("Usage: /tool write <path> then put file contents on the next lines")
    if not separator:
        raise ValueError("Put the file contents on the lines after `/tool write <path>`.")
    return path.strip(), content


def partition_calendar_payload(payload: str, usage: str) -> tuple[str, str]:
    query, sep, value = payload.partition("|")
    query = clean_query(query)
    value = value.strip()
    if not sep or not query or not value:
        raise ValueError(usage)
    return query, value


def extract_calendar_create_text(message: str) -> str | None:
    lower = message.lower()
    if "calendar" not in lower:
        return None
    if not any(
        lower.startswith(prefix)
        for prefix in ("add ", "create ", "schedule ", "put ", "please add ", "please create ", "please schedule ", "please put ")
    ):
        return None

    candidate = re.sub(r"^(?:please\s+)?(?:add|create|schedule|put)\s+", "", message, flags=re.IGNORECASE)
    candidate = re.sub(r"\s+(?:to|on|in)\s+(?:my\s+)?calendar\b", "", candidate, flags=re.IGNORECASE).strip()
    cleaned = clean_query(candidate)
    return cleaned or None


def normalize_confirmation_text(text: str) -> str:
    return str(text or "").strip().lower().rstrip(".!")


def clean_query(value: str) -> str:
    return str(value or "").strip().rstrip("?.!,")

