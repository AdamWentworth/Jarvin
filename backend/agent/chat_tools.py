from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

import config as cfg
from backend.agent import tools
from backend.agent.briefing_tools import (
    handle_brief_command,
    maybe_handle_brief_request,
)
from backend.agent.calendar_tools import (
    CalendarPlan,
    maybe_plan_calendar_request,
)
from backend.agent.followup_context import (
    get_active_follow_up_domain,
    remember_active_follow_up_domain,
)
from backend.agent.followup_router import (
    has_conflicting_domain_cues,
    looks_like_ambiguous_follow_up,
)
from backend.agent.reminder_tools import (
    handle_reminder_command,
    maybe_handle_reminder_request,
)
from backend.agent.research_tools import (
    maybe_plan_research_request,
    remember_research_context,
)
from backend.agent.weather_tools import (
    maybe_handle_weather_request,
)
from backend.agent.workspace_tools import (
    maybe_plan_workspace_request,
    remember_workspace_context,
)
from backend.ai_engine import build_jarvin_config, generate_reply
from backend.agent.external_tools import (
    begin_google_calendar_auth,
    browse_search_results,
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
    tool_kind: str | None = None
    tool_payload: dict[str, object] | None = None
    active_domain: str | None = None


def maybe_handle_assistant_tool_request(text: str, *, conversation_id: int | None = None) -> ToolChatResponse:
    pending = _maybe_handle_pending_confirmation(text, conversation_id=conversation_id)
    if pending.handled:
        return _finalize_tool_response(pending, conversation_id=conversation_id)

    explicit = maybe_handle_tool_command(text, conversation_id=conversation_id)
    if explicit.handled:
        return _finalize_tool_response(explicit, conversation_id=conversation_id)

    natural = maybe_handle_natural_language_tool_request(text, conversation_id=conversation_id)
    return _finalize_tool_response(natural, conversation_id=conversation_id)


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
        return _safe_tool_call(lambda: _list_reply(rest or "."), "I couldn't list that directory.", active_domain="workspace")
    if verb == "search":
        return _safe_tool_call(lambda: _repo_search_reply(rest), "I couldn't search the workspace.", active_domain="workspace")
    if verb == "read":
        return _safe_tool_call(lambda: _read_reply(rest), "I couldn't read that file.", active_domain="workspace")
    if verb in {"write", "append"}:
        return _safe_tool_call(lambda: _write_reply(rest, append=verb == "append"), "I couldn't write that file.", active_domain="workspace")
    if verb == "run":
        return _safe_tool_call(lambda: _run_reply(rest), "I couldn't run that command.", active_domain="workspace")
    if verb == "web":
        return _safe_tool_call(lambda: _web_search_reply(rest), "I couldn't search the web just now.", active_domain="research")
    if verb == "google":
        return _safe_tool_call(lambda: _google_search_reply(rest, natural=False), "I couldn't use Google search just now.", active_domain="research")
    if verb == "weather":
        return _safe_weather_tool_response(rest, conversation_id=conversation_id)
    if verb == "brief":
        return _safe_tool_call(lambda: handle_brief_command(rest), "I couldn't build the morning brief just now.", active_domain="brief")
    if verb == "reminder":
        return _safe_tool_call(lambda: handle_reminder_command(rest), "I couldn't manage reminders just now.", active_domain="reminder")
    if verb == "calendar":
        return _safe_tool_call(
            lambda: _calendar_command_reply(rest, conversation_id=conversation_id),
            "I couldn't work with your calendar just now.",
            active_domain="calendar",
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
        return _safe_tool_call(
            lambda: begin_google_calendar_auth(),
            "I couldn't start Google Calendar authorization.",
            active_domain="calendar",
        )

    active_follow_up = _maybe_active_follow_up_response(message, conversation_id=conversation_id)
    if active_follow_up is not None:
        return active_follow_up

    weather_reply = _maybe_weather_tool_response(message, conversation_id=conversation_id)
    if weather_reply is not None:
        return weather_reply

    brief_reply = maybe_handle_brief_request(message, conversation_id=conversation_id)
    if brief_reply is not None:
        return ToolChatResponse(handled=True, reply=brief_reply, active_domain="brief")

    reminder_reply = maybe_handle_reminder_request(message, conversation_id=conversation_id)
    if reminder_reply is not None:
        return ToolChatResponse(handled=True, reply=reminder_reply, active_domain="reminder")

    calendar_reply = _maybe_calendar_tool_response(message, conversation_id=conversation_id)
    if calendar_reply is not None:
        return calendar_reply

    workspace_reply = _maybe_workspace_tool_response(message, conversation_id=conversation_id)
    if workspace_reply is not None:
        return workspace_reply

    research_reply = _maybe_research_tool_response(message, conversation_id=conversation_id)
    if research_reply is not None:
        return research_reply

    details_match = _CALENDAR_DETAILS_RE.search(message)
    if details_match:
        query = _clean_query(details_match.group("query"))
        return _safe_tool_call(lambda: _calendar_details_reply(query), "I couldn't open that calendar event.", active_domain="calendar")

    calendar_create = _extract_calendar_create_text(message)
    if calendar_create:
        return _safe_tool_call(lambda: _calendar_create_reply(calendar_create), "I couldn't create that calendar event.", active_domain="calendar")

    rename_match = _CALENDAR_RENAME_RE.search(message) or _CALENDAR_TITLE_RE.search(message)
    if rename_match:
        query = _clean_query(rename_match.group("query"))
        new_title = _clean_query(rename_match.group("new_title"))
        return _safe_tool_call(
            lambda: _calendar_update_request_reply(query, conversation_id=conversation_id, title=new_title),
            "I couldn't prepare that calendar title change.",
            active_domain="calendar",
        )

    location_match = _CALENDAR_LOCATION_RE.search(message)
    if location_match:
        query = _clean_query(location_match.group("query"))
        location = location_match.group("location").strip()
        return _safe_tool_call(
            lambda: _calendar_update_request_reply(query, conversation_id=conversation_id, location=location),
            "I couldn't prepare that calendar location change.",
            active_domain="calendar",
        )

    clear_location_match = _CALENDAR_CLEAR_LOCATION_RE.search(message)
    if clear_location_match:
        query = _clean_query(clear_location_match.group("query"))
        return _safe_tool_call(
            lambda: _calendar_update_request_reply(query, conversation_id=conversation_id, location=""),
            "I couldn't prepare that calendar location update.",
            active_domain="calendar",
        )

    notes_match = _CALENDAR_NOTES_RE.search(message)
    if notes_match:
        query = _clean_query(notes_match.group("query"))
        description = notes_match.group("description").strip()
        return _safe_tool_call(
            lambda: _calendar_update_request_reply(query, conversation_id=conversation_id, description=description),
            "I couldn't prepare that calendar notes update.",
            active_domain="calendar",
        )

    clear_notes_match = _CALENDAR_CLEAR_NOTES_RE.search(message)
    if clear_notes_match:
        query = _clean_query(clear_notes_match.group("query"))
        return _safe_tool_call(
            lambda: _calendar_update_request_reply(query, conversation_id=conversation_id, description=""),
            "I couldn't prepare that calendar notes update.",
            active_domain="calendar",
        )

    delete_match = _CALENDAR_DELETE_RE.search(message)
    if delete_match:
        query = _clean_query(delete_match.group("query"))
        return _safe_tool_call(
            lambda: _calendar_delete_request_reply(query, conversation_id=conversation_id),
            "I couldn't prepare that calendar deletion.",
            active_domain="calendar",
        )

    move_match = _CALENDAR_MOVE_RE.search(message)
    if move_match:
        query = _clean_query(move_match.group("query"))
        when_text = _clean_query(move_match.group("when"))
        return _safe_tool_call(
            lambda: _calendar_move_request_reply(query, when_text, conversation_id=conversation_id),
            "I couldn't prepare that calendar update.",
            active_domain="calendar",
        )

    if _CALENDAR_LOOKUP_RE.search(message):
        return _safe_tool_call(lambda: _calendar_lookup_reply(message), "I couldn't check your calendar just now.", active_domain="calendar")

    weather_match = _WEATHER_RE.search(message)
    if weather_match:
        location = _clean_query(weather_match.group("location"))
        return _safe_tool_call(lambda: _weather_reply(location), "I couldn't check the weather just now.", active_domain="weather")

    google_match = _GOOGLE_RE.search(message)
    if google_match:
        query = _clean_query(google_match.group("query"))
        return _safe_tool_call(lambda: _google_search_reply(query, natural=True), "I couldn't search the web just now.", active_domain="research")

    web_match = _WEB_SEARCH_RE.search(message)
    if web_match:
        query = _clean_query(web_match.group("query"))
        return _safe_tool_call(lambda: _web_search_reply(query), "I couldn't search the web just now.", active_domain="research")

    repo_match = _REPO_SEARCH_RE.search(message)
    if repo_match:
        query = _clean_query(repo_match.group("query"))
        return _safe_tool_call(lambda: _repo_search_reply(query), "I couldn't search the workspace.", active_domain="workspace")

    lower = message.lower()
    if lower.startswith("search the repo for ") or lower.startswith("search the codebase for ") or lower.startswith("search the workspace for "):
        query = _clean_query(message.split(" for ", 1)[1])
        return _safe_tool_call(lambda: _repo_search_reply(query), "I couldn't search the workspace.", active_domain="workspace")
    if lower.startswith("find ") and (" in the repo" in lower or " in the codebase" in lower or " in the workspace" in lower):
        query = _clean_query(re.split(r"\s+in\s+the\s+(?:repo|codebase|workspace)$", message, maxsplit=1, flags=re.IGNORECASE)[0][5:])
        return _safe_tool_call(lambda: _repo_search_reply(query), "I couldn't search the workspace.", active_domain="workspace")

    read_match = _READ_FILE_RE.search(message)
    if read_match:
        return _safe_tool_call(
            lambda: _read_file_reply(
                read_match.group("path"),
                int(read_match.group("start")) if read_match.group("start") else 1,
                int(read_match.group("end")) if read_match.group("end") else None,
            ),
            "I couldn't read that file.",
            active_domain="workspace",
        )

    list_match = _LIST_DIR_RE.search(message)
    if list_match:
        return _safe_tool_call(lambda: _list_reply(list_match.group("path")), "I couldn't list that directory.", active_domain="workspace")

    run_match = _RUN_RE.search(message)
    if run_match:
        return _safe_tool_call(lambda: _run_reply(run_match.group("command")), "I couldn't run that command.", active_domain="workspace")

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
            active_domain="calendar",
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
            active_domain="calendar",
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
            active_domain="calendar",
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


def _finalize_tool_response(response: ToolChatResponse, *, conversation_id: int | None) -> ToolChatResponse:
    if response.handled and response.active_domain:
        remember_active_follow_up_domain(conversation_id, response.active_domain)
    return response


def _safe_tool_call(fn: Callable[[], str], fallback: str, *, active_domain: str | None = None) -> ToolChatResponse:
    try:
        return ToolChatResponse(handled=True, reply=fn(), active_domain=active_domain)
    except Exception as exc:
        detail = str(exc).strip()
        if detail:
            return ToolChatResponse(handled=True, reply=f"{fallback} {detail}", active_domain=active_domain)
        return ToolChatResponse(handled=True, reply=fallback, active_domain=active_domain)


def _maybe_active_follow_up_response(text: str, *, conversation_id: int | None) -> ToolChatResponse | None:
    active_domain = get_active_follow_up_domain(conversation_id)
    if active_domain is None:
        return None
    if not looks_like_ambiguous_follow_up(text):
        return None
    if has_conflicting_domain_cues(text, active_domain=active_domain):
        return None
    return _dispatch_active_follow_up(active_domain, text, conversation_id=conversation_id)


def _dispatch_active_follow_up(active_domain: str, text: str, *, conversation_id: int | None) -> ToolChatResponse | None:
    if active_domain == "weather":
        return _maybe_weather_tool_response(text, conversation_id=conversation_id)
    if active_domain == "brief":
        reply = maybe_handle_brief_request(text, conversation_id=conversation_id)
        if reply is None:
            return None
        return ToolChatResponse(handled=True, reply=reply, active_domain="brief")
    if active_domain == "reminder":
        reply = maybe_handle_reminder_request(text, conversation_id=conversation_id)
        if reply is None:
            return None
        return ToolChatResponse(handled=True, reply=reply, active_domain="reminder")
    if active_domain == "calendar":
        return _maybe_calendar_tool_response(text, conversation_id=conversation_id)
    if active_domain == "workspace":
        return _maybe_workspace_tool_response(text, conversation_id=conversation_id)
    if active_domain == "research":
        return _maybe_research_tool_response(text, conversation_id=conversation_id)
    return None


def _safe_weather_tool_response(rest: str, *, conversation_id: int | None) -> ToolChatResponse:
    try:
        response = maybe_handle_weather_request(f"weather for {rest}".strip(), conversation_id=conversation_id)
        if response is None:
            return ToolChatResponse(handled=True, reply="I couldn't understand that weather request yet.")
        return ToolChatResponse(
            handled=True,
            reply=response.reply,
            tool_kind="weather" if response.payload else None,
            tool_payload=response.payload or None,
            active_domain="weather",
        )
    except Exception as exc:
        detail = str(exc).strip()
        return ToolChatResponse(
            handled=True,
            reply=f"I couldn't check the weather just now. {detail}".strip(),
            active_domain="weather",
        )


def _maybe_weather_tool_response(text: str, *, conversation_id: int | None) -> ToolChatResponse | None:
    try:
        response = maybe_handle_weather_request(text, conversation_id=conversation_id)
    except Exception as exc:
        detail = str(exc).strip()
        return ToolChatResponse(
            handled=True,
            reply=f"I couldn't check the weather just now. {detail}".strip(),
        )
    if response is None:
        return None
    return ToolChatResponse(
        handled=True,
        reply=response.reply,
        tool_kind="weather" if response.payload else None,
        tool_payload=response.payload or None,
        active_domain="weather",
    )


def _maybe_calendar_tool_response(text: str, *, conversation_id: int | None) -> ToolChatResponse | None:
    plan = maybe_plan_calendar_request(text, conversation_id=conversation_id)
    if plan is None:
        return None
    try:
        return ToolChatResponse(
            handled=True,
            reply=_execute_calendar_plan(plan, raw_message=text, conversation_id=conversation_id),
            active_domain="calendar",
        )
    except Exception as exc:
        detail = str(exc).strip()
        return ToolChatResponse(
            handled=True,
            reply=f"I couldn't work with your calendar just now. {detail}".strip(),
            active_domain="calendar",
        )


def _maybe_workspace_tool_response(text: str, *, conversation_id: int | None) -> ToolChatResponse | None:
    plan = maybe_plan_workspace_request(text, conversation_id=conversation_id)
    if plan is None or plan.action == "unknown":
        return None
    try:
        return ToolChatResponse(
            handled=True,
            reply=_execute_workspace_plan(plan, conversation_id=conversation_id),
            active_domain="workspace",
        )
    except Exception as exc:
        detail = str(exc).strip()
        return ToolChatResponse(
            handled=True,
            reply=f"I couldn't work with the local workspace just now. {detail}".strip(),
            active_domain="workspace",
        )


def _maybe_research_tool_response(text: str, *, conversation_id: int | None) -> ToolChatResponse | None:
    plan = maybe_plan_research_request(text, conversation_id=conversation_id)
    if plan is None or plan.action == "unknown":
        return None
    try:
        return ToolChatResponse(
            handled=True,
            reply=_execute_research_plan(plan, conversation_id=conversation_id),
            active_domain="research",
        )
    except Exception as exc:
        detail = str(exc).strip()
        return ToolChatResponse(
            handled=True,
            reply=f"I couldn't search the web just now. {detail}".strip(),
            active_domain="research",
        )


def _execute_calendar_plan(plan: CalendarPlan, *, raw_message: str, conversation_id: int | None) -> str:
    action = (plan.action or "lookup").strip().lower()

    if action == "auth":
        return begin_google_calendar_auth()

    if action == "lookup":
        return _calendar_lookup_reply(raw_message, window_days_override=plan.window_days)

    if action == "create":
        details = plan.query or _extract_calendar_create_text(raw_message)
        if not details:
            raise ValueError("Tell me what event to create and when it should happen.")
        return _calendar_create_reply(details)

    if action == "details":
        query = plan.query or raw_message
        return _calendar_details_reply(query)

    if action == "delete":
        query = plan.query or raw_message
        return _calendar_delete_request_reply(query, conversation_id=conversation_id)

    if action == "rename":
        query = plan.query or raw_message
        if not plan.new_title:
            raise ValueError("Tell me the new event title too.")
        return _calendar_update_request_reply(query, conversation_id=conversation_id, title=plan.new_title)

    if action == "update_location":
        query = plan.query or raw_message
        if plan.new_location is None:
            raise ValueError("Tell me the new event location too.")
        return _calendar_update_request_reply(query, conversation_id=conversation_id, location=plan.new_location)

    if action == "update_description":
        query = plan.query or raw_message
        if plan.new_description is None:
            raise ValueError("Tell me the new event notes too.")
        return _calendar_update_request_reply(query, conversation_id=conversation_id, description=plan.new_description)

    if action == "move":
        query = plan.query or raw_message
        when_text = plan.when_text or raw_message
        return _calendar_move_request_reply(query, when_text, conversation_id=conversation_id)

    return _calendar_lookup_reply(raw_message, window_days_override=plan.window_days)


def _execute_workspace_plan(plan, *, conversation_id: int | None) -> str:
    action = str(plan.action or "").strip().lower()

    if action == "search_repo":
        query = _clean_query(plan.query or "")
        if not query:
            raise ValueError("Tell me what to search for in the repo.")
        reply = _repo_search_reply(query)
        remember_workspace_context(conversation_id, action="search_repo", query=query)
        return reply

    if action == "read_file":
        path = _clean_query(plan.path or "")
        if not path:
            raise ValueError("Tell me which file to read.")
        start_line = int(plan.start_line or 1)
        end_line = int(plan.end_line) if plan.end_line is not None else None
        reply = _read_file_reply(path, start_line, end_line)
        inferred_end = end_line if end_line is not None else start_line + int(cfg.settings.agent_max_file_read_lines) - 1
        remember_workspace_context(
            conversation_id,
            action="read_file",
            path=path,
            start_line=start_line,
            end_line=inferred_end,
        )
        return reply

    if action == "list_directory":
        path = _clean_query(plan.path or ".") or "."
        reply = _list_reply(path)
        remember_workspace_context(conversation_id, action="list_directory", path=path)
        return reply

    if action == "run_command":
        command = _clean_query(plan.command or "")
        if not command:
            raise ValueError("Tell me which safe command to run.")
        reply = _run_reply(command)
        remember_workspace_context(conversation_id, action="run_command", command=command)
        return reply

    raise ValueError(f"Unsupported workspace action `{action}`.")


def _execute_research_plan(plan, *, conversation_id: int | None) -> str:
    action = str(plan.action or "").strip().lower()
    query = _clean_query(plan.query or "")
    if not query:
        raise ValueError("Tell me what you want me to research.")

    if action == "google_search":
        reply = _google_search_reply(query, natural=True)
        remember_research_context(conversation_id, action="google_search", query=query)
        return reply

    reply = _web_search_reply(query)
    remember_research_context(conversation_id, action="web_search", query=query)
    return reply


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


def _calendar_lookup_reply(raw: str, *, window_days_override: int | None = None) -> str:
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

    window_days = int(window_days_override or _infer_calendar_window_days(raw))
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
    research = browse_search_results(query)
    return _render_web_research_reply(research, label="Web")


def _google_search_reply(query: str, *, natural: bool) -> str:
    provider = str(cfg.settings.agent_web_search_provider or "").strip().lower()
    if provider != "google_cse":
        if natural:
            research = browse_search_results(query)
            note = (
                "Google search is not configured on this host, so I used the current web search provider instead.\n\n"
                if not google_search_is_configured()
                else "Google search is not the active provider on this host, so I used the current web search provider instead.\n\n"
            )
            return note + _render_web_research_reply(research, label="Web")
        return (
            "Google search is not the active provider on this host. "
            "Set `JARVIN_AGENT_WEB_SEARCH_PROVIDER=google_cse` with valid Google search credentials, "
            "or use `/tool web <query>` for the current web-search provider."
        )

    research = browse_search_results(query)
    return _render_web_research_reply(research, label="Google")


def _render_web_research_reply(research, *, label: str) -> str:
    if getattr(research, "pages", None):
        summary = _summarize_web_research(research)
        if not summary:
            summary = _fallback_web_research_summary(research)
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


def _summarize_web_research(research) -> str:
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
    cfg = build_jarvin_config(
        mode="agent_strong",
        system_instructions=system,
        temperature=0.2,
        max_tokens=320,
    )
    prompt = (
        f"Search query: {research.query}\n"
        "Answer from the source notes below. Prefer direct usefulness over verbosity."
    )
    return generate_reply(prompt, cfg=cfg, context="\n\n".join(source_blocks)).strip()


def _fallback_web_research_summary(research) -> str:
    bullets = []
    for index, page in enumerate(research.pages, start=1):
        first_line = page.excerpt.splitlines()[0].strip() if page.excerpt else ""
        snippet = first_line[:220].rstrip()
        bullets.append(f"- [{index}] {page.title}: {snippet}")
    return "\n".join(bullets)


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
