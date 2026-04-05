from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import config as cfg
import backend.agent.host_tool_runtime as host_tool_runtime
from backend.agent.host_action_approvals import (
    PendingHostApproval, build_approval_payload, clear_pending_host_approval, get_host_action_trust,
    get_pending_host_approval, grant_host_action_trust, normalize_agent_access_mode, set_pending_host_approval,
)
from backend.agent.briefing.brief_request_tools import handle_brief_command, maybe_handle_brief_request
from backend.agent.calendar.calendar_request_tools import CalendarPlan, maybe_plan_calendar_request
from backend.agent.chat.chat_intent_patterns import (
    CALENDAR_AUTH_RE as _CALENDAR_AUTH_RE,
    CALENDAR_CLEAR_LOCATION_RE as _CALENDAR_CLEAR_LOCATION_RE,
    CALENDAR_CLEAR_NOTES_RE as _CALENDAR_CLEAR_NOTES_RE,
    CALENDAR_DELETE_RE as _CALENDAR_DELETE_RE,
    CALENDAR_DETAILS_RE as _CALENDAR_DETAILS_RE,
    CALENDAR_LOCATION_RE as _CALENDAR_LOCATION_RE,
    CALENDAR_LOOKUP_RE as _CALENDAR_LOOKUP_RE,
    CALENDAR_MOVE_RE as _CALENDAR_MOVE_RE,
    CALENDAR_NOTES_RE as _CALENDAR_NOTES_RE,
    CALENDAR_RENAME_RE as _CALENDAR_RENAME_RE,
    CALENDAR_TITLE_RE as _CALENDAR_TITLE_RE,
    CANCEL_PATTERNS as _CANCEL_PATTERNS,
    CONFIRM_PATTERNS as _CONFIRM_PATTERNS,
    GOOGLE_RE as _GOOGLE_RE,
    LIST_DIR_RE as _LIST_DIR_RE,
    READ_FILE_RE as _READ_FILE_RE,
    REPO_SEARCH_RE as _REPO_SEARCH_RE,
    RUN_RE as _RUN_RE,
    WEB_SEARCH_RE as _WEB_SEARCH_RE,
)
from backend.agent.chat.chat_domain_dispatch import (
    dispatch_active_follow_up_impl, execute_calendar_plan_impl, execute_research_plan_impl, execute_workspace_plan_impl,
    maybe_active_follow_up_response_impl, maybe_calendar_tool_response_impl, maybe_research_tool_response_impl,
    maybe_weather_tool_response_impl, maybe_workspace_tool_response_impl, safe_weather_tool_response_impl,
)
from backend.agent.chat.chat_domain_adapters import (
    execute_calendar_plan_adapter, execute_research_plan_adapter, maybe_calendar_tool_response_adapter,
    maybe_research_tool_response_adapter, maybe_workspace_tool_response_adapter,
)
from backend.agent.chat.chat_tool_entrypoints import (
    help_reply as help_reply_impl,
    maybe_handle_natural_language_tool_request_impl,
    maybe_handle_tool_command_impl,
)
from backend.agent.chat.chat_tool_helpers import (
    calendar_command_reply as _calendar_command_reply,
    calendar_create_reply as _calendar_create_reply,
    calendar_delete_request_reply as _calendar_delete_request_reply,
    calendar_details_reply as _calendar_details_reply,
    calendar_field_update_success_reply as _calendar_field_update_success_reply,
    calendar_lookup_reply as _calendar_lookup_reply,
    calendar_move_request_reply as _calendar_move_request_reply,
    calendar_update_request_reply as _calendar_update_request_reply,
    clean_query as _clean_query,
    extract_calendar_create_text as _extract_calendar_create_text,
    infer_calendar_window_days as _infer_calendar_window_days,
    list_reply as _list_reply,
    google_search_reply as _google_search_reply,
    normalize_confirmation_text as _normalize_confirmation_text,
    parse_read_args as _parse_read_args,
    parse_write_args as _parse_write_args,
    read_file_reply as _read_file_reply,
    read_reply as _read_reply,
    repo_search_reply as _repo_search_reply,
    run_reply as _run_reply,
    web_search_reply as _web_search_reply,
)
from backend.agent.chat.chat_host_action_approval_flow import (
    execute_pending_host_approval_impl, guard_command_tool_response_impl, guard_write_tool_command_impl,
)
from backend.agent.chat.chat_pending_actions import maybe_handle_pending_confirmation_impl
from backend.agent.integration_facade import (
    begin_google_calendar_auth,
    delete_calendar_event,
    reschedule_calendar_event,
    update_calendar_event_fields,
)
from backend.agent.chat.chat_followup_context import get_active_follow_up_domain, remember_active_follow_up_domain
from backend.agent.chat.chat_followup_router import has_conflicting_domain_cues, looks_like_ambiguous_follow_up
from backend.agent.chat.chat_response_utils import finalize_tool_response_impl, safe_tool_call_impl
from backend.agent.calendar_pending_actions import clear_pending_calendar_action, get_pending_calendar_action
from backend.agent.reminders.reminder_request_tools import handle_reminder_command, maybe_handle_reminder_request
from backend.agent.research.research_request_tools import maybe_plan_research_request, remember_research_context
from backend.agent.weather.weather_request_tools import maybe_handle_weather_request
from backend.agent.workspace.workspace_request_tools import maybe_plan_workspace_request, remember_workspace_context
from memory.agent_action_log import log_agent_action_event
from memory.conversation import update_latest_tool_turn

tools = host_tool_runtime


@dataclass(frozen=True)
class ToolChatResponse:
    handled: bool
    reply: str = ""
    tool_kind: str | None = None
    tool_payload: dict[str, object] | None = None
    active_domain: str | None = None


def maybe_handle_assistant_tool_request(
    text: str,
    *,
    conversation_id: int | None = None,
    client_session_id: str | None = None,
    agent_access_mode: str | None = None,
) -> ToolChatResponse:
    pending = _maybe_handle_pending_confirmation(
        text,
        conversation_id=conversation_id,
        client_session_id=client_session_id,
    )
    if pending.handled:
        return _finalize_tool_response(pending, conversation_id=conversation_id)

    explicit = maybe_handle_tool_command(
        text,
        conversation_id=conversation_id,
        client_session_id=client_session_id,
        agent_access_mode=agent_access_mode,
    )
    if explicit.handled:
        return _finalize_tool_response(explicit, conversation_id=conversation_id)

    natural = maybe_handle_natural_language_tool_request(
        text,
        conversation_id=conversation_id,
        client_session_id=client_session_id,
        agent_access_mode=agent_access_mode,
    )
    return _finalize_tool_response(natural, conversation_id=conversation_id)


def maybe_handle_tool_command(
    text: str,
    *,
    conversation_id: int | None = None,
    client_session_id: str | None = None,
    agent_access_mode: str | None = None,
) -> ToolChatResponse:
    return maybe_handle_tool_command_impl(
        text,
        conversation_id=conversation_id,
        client_session_id=client_session_id,
        agent_access_mode=agent_access_mode,
        ToolChatResponse=ToolChatResponse,
        tools=tools,
        list_reply=_list_reply,
        repo_search_reply=_repo_search_reply,
        read_reply=_read_reply,
        guard_write_tool_command=_guard_write_tool_command,
        guard_command_tool_response=_guard_command_tool_response,
        web_search_reply=_web_search_reply,
        google_search_reply=_google_search_reply,
        safe_weather_tool_response=_safe_weather_tool_response,
        handle_brief_command=handle_brief_command,
        handle_reminder_command=handle_reminder_command,
        calendar_command_reply=_calendar_command_reply,
    )


def maybe_handle_natural_language_tool_request(
    text: str,
    *,
    conversation_id: int | None = None,
    client_session_id: str | None = None,
    agent_access_mode: str | None = None,
) -> ToolChatResponse:
    return maybe_handle_natural_language_tool_request_impl(
        text,
        conversation_id=conversation_id,
        client_session_id=client_session_id,
        agent_access_mode=agent_access_mode,
        ToolChatResponse=ToolChatResponse,
        calendar_auth_re=_CALENDAR_AUTH_RE,
        begin_google_calendar_auth=begin_google_calendar_auth,
        maybe_active_follow_up_response=_maybe_active_follow_up_response,
        maybe_weather_tool_response=_maybe_weather_tool_response,
        maybe_handle_brief_request=maybe_handle_brief_request,
        maybe_handle_reminder_request=maybe_handle_reminder_request,
        maybe_calendar_tool_response=_maybe_calendar_tool_response,
        maybe_workspace_tool_response=_maybe_workspace_tool_response,
        maybe_research_tool_response=_maybe_research_tool_response,
        calendar_details_re=_CALENDAR_DETAILS_RE,
        clean_query=_clean_query,
        safe_tool_call=_safe_tool_call,
        calendar_details_reply=_calendar_details_reply,
        extract_calendar_create_text=_extract_calendar_create_text,
        calendar_create_reply=_calendar_create_reply,
        calendar_rename_re=_CALENDAR_RENAME_RE,
        calendar_title_re=_CALENDAR_TITLE_RE,
        calendar_update_request_reply=_calendar_update_request_reply,
        calendar_location_re=_CALENDAR_LOCATION_RE,
        calendar_clear_location_re=_CALENDAR_CLEAR_LOCATION_RE,
        calendar_notes_re=_CALENDAR_NOTES_RE,
        calendar_clear_notes_re=_CALENDAR_CLEAR_NOTES_RE,
        calendar_delete_re=_CALENDAR_DELETE_RE,
        calendar_delete_request_reply=_calendar_delete_request_reply,
        calendar_move_re=_CALENDAR_MOVE_RE,
        calendar_move_request_reply=_calendar_move_request_reply,
        infer_calendar_window_days=_infer_calendar_window_days,
        calendar_lookup_re=_CALENDAR_LOOKUP_RE,
        calendar_lookup_reply=_calendar_lookup_reply,
        web_search_re=_WEB_SEARCH_RE,
        google_re=_GOOGLE_RE,
        repo_search_re=_REPO_SEARCH_RE,
        web_search_reply=_web_search_reply,
        google_search_reply=_google_search_reply,
        repo_search_reply=_repo_search_reply,
        read_file_re=_READ_FILE_RE,
        parse_read_args=_parse_read_args,
        read_file_reply=_read_file_reply,
        list_dir_re=_LIST_DIR_RE,
        list_reply=_list_reply,
        run_re=_RUN_RE,
        guard_command_tool_response=_guard_command_tool_response,
    )


def _maybe_handle_pending_confirmation(
    text: str,
    *,
    conversation_id: int | None,
    client_session_id: str | None,
) -> ToolChatResponse:
    return maybe_handle_pending_confirmation_impl(
        text,
        conversation_id=conversation_id,
        client_session_id=client_session_id,
        ToolChatResponse=ToolChatResponse,
        get_pending_host_approval=get_pending_host_approval,
        normalize_confirmation_text=_normalize_confirmation_text,
        cancel_patterns=_CANCEL_PATTERNS,
        confirm_patterns=_CONFIRM_PATTERNS,
        trust_conversation_patterns={"trust this chat", "trust this conversation", "approve for this chat"},
        trust_session_patterns={"trust this session", "approve for this session", "trust this device"},
        update_latest_tool_turn=update_latest_tool_turn,
        build_approval_payload=build_approval_payload,
        clear_pending_host_approval=clear_pending_host_approval,
        grant_host_action_trust=grant_host_action_trust,
        execute_pending_host_approval=_execute_pending_host_approval,
        log_agent_action_event=log_agent_action_event,
        get_pending_calendar_action=get_pending_calendar_action,
        clear_pending_calendar_action=clear_pending_calendar_action,
        delete_calendar_event=delete_calendar_event,
        reschedule_calendar_event=reschedule_calendar_event,
        update_calendar_event_fields=update_calendar_event_fields,
        calendar_field_update_success_reply=_calendar_field_update_success_reply,
    )
def _execute_pending_host_approval(
    pending: PendingHostApproval,
    *,
    conversation_id: int | None,
    client_session_id: str | None,
) -> ToolChatResponse:
    return execute_pending_host_approval_impl(
        pending,
        conversation_id=conversation_id,
        client_session_id=client_session_id,
        ToolChatResponse=ToolChatResponse,
        clean_query=_clean_query,
        run_reply=_run_reply,
        remember_workspace_context=remember_workspace_context,
        tools=tools,
        log_agent_action_event=log_agent_action_event,
        access_mode="approve_risky",
    )
def _guard_command_tool_response(
    command: str,
    *,
    conversation_id: int | None,
    client_session_id: str | None,
    agent_access_mode: str | None,
) -> ToolChatResponse:
    return guard_command_tool_response_impl(
        command,
        conversation_id=conversation_id,
        client_session_id=client_session_id,
        agent_access_mode=agent_access_mode,
        ToolChatResponse=ToolChatResponse,
        clean_query=_clean_query,
        normalize_agent_access_mode=normalize_agent_access_mode,
        run_reply=_run_reply,
        remember_workspace_context=remember_workspace_context,
        tools=tools,
        PendingHostApproval=PendingHostApproval,
        set_pending_host_approval=set_pending_host_approval,
        build_approval_payload=build_approval_payload,
        get_host_action_trust=get_host_action_trust,
        log_agent_action_event=log_agent_action_event,
    )
def _guard_write_tool_command(
    rest: str,
    *,
    append: bool,
    conversation_id: int | None,
    client_session_id: str | None,
    agent_access_mode: str | None,
) -> ToolChatResponse:
    return guard_write_tool_command_impl(
        rest,
        append=append,
        conversation_id=conversation_id,
        client_session_id=client_session_id,
        agent_access_mode=agent_access_mode,
        ToolChatResponse=ToolChatResponse,
        parse_write_args=_parse_write_args,
        normalize_agent_access_mode=normalize_agent_access_mode,
        tools=tools,
        remember_workspace_context=remember_workspace_context,
        PendingHostApproval=PendingHostApproval,
        set_pending_host_approval=set_pending_host_approval,
        build_approval_payload=build_approval_payload,
        get_host_action_trust=get_host_action_trust,
        log_agent_action_event=log_agent_action_event,
    )
def _help_reply() -> str:
    return help_reply_impl(tools)
def _finalize_tool_response(response: ToolChatResponse, *, conversation_id: int | None) -> ToolChatResponse:
    return finalize_tool_response_impl(
        response,
        conversation_id=conversation_id,
        remember_active_follow_up_domain=remember_active_follow_up_domain,
    )
def _safe_tool_call(fn: Callable[[], str], fallback: str, *, active_domain: str | None = None) -> ToolChatResponse:
    return safe_tool_call_impl(
        ToolChatResponse=ToolChatResponse,
        fn=fn,
        fallback=fallback,
        active_domain=active_domain,
    )
def _maybe_active_follow_up_response(
    text: str,
    *,
    conversation_id: int | None,
    client_session_id: str | None,
    agent_access_mode: str | None,
) -> ToolChatResponse | None:
    return maybe_active_follow_up_response_impl(
        text,
        conversation_id=conversation_id,
        client_session_id=client_session_id,
        agent_access_mode=agent_access_mode,
        get_active_follow_up_domain=get_active_follow_up_domain,
        looks_like_ambiguous_follow_up=looks_like_ambiguous_follow_up,
        has_conflicting_domain_cues=has_conflicting_domain_cues,
        dispatch_active_follow_up=_dispatch_active_follow_up,
    )
def _dispatch_active_follow_up(
    active_domain: str,
    text: str,
    *,
    conversation_id: int | None,
    client_session_id: str | None,
    agent_access_mode: str | None,
) -> ToolChatResponse | None:
    return dispatch_active_follow_up_impl(
        active_domain,
        text,
        conversation_id=conversation_id,
        client_session_id=client_session_id,
        agent_access_mode=agent_access_mode,
        maybe_weather_tool_response=_maybe_weather_tool_response,
        maybe_handle_brief_request=maybe_handle_brief_request,
        maybe_handle_reminder_request=maybe_handle_reminder_request,
        maybe_calendar_tool_response=_maybe_calendar_tool_response,
        maybe_workspace_tool_response=_maybe_workspace_tool_response,
        maybe_research_tool_response=_maybe_research_tool_response,
        ToolChatResponse=ToolChatResponse,
    )
def _safe_weather_tool_response(rest: str, *, conversation_id: int | None) -> ToolChatResponse:
    return safe_weather_tool_response_impl(
        rest,
        conversation_id=conversation_id,
        ToolChatResponse=ToolChatResponse,
        maybe_handle_weather_request=maybe_handle_weather_request,
    )
def _maybe_weather_tool_response(text: str, *, conversation_id: int | None) -> ToolChatResponse | None:
    return maybe_weather_tool_response_impl(
        text,
        conversation_id=conversation_id,
        ToolChatResponse=ToolChatResponse,
        maybe_handle_weather_request=maybe_handle_weather_request,
    )
def _maybe_calendar_tool_response(text: str, *, conversation_id: int | None) -> ToolChatResponse | None:
    return maybe_calendar_tool_response_adapter(
        text,
        conversation_id=conversation_id,
        ToolChatResponse=ToolChatResponse,
        maybe_plan_calendar_request=maybe_plan_calendar_request,
        execute_calendar_plan=_execute_calendar_plan,
        maybe_calendar_tool_response_impl=maybe_calendar_tool_response_impl,
    )
def _maybe_workspace_tool_response(
    text: str,
    *,
    conversation_id: int | None,
    client_session_id: str | None,
    agent_access_mode: str | None,
) -> ToolChatResponse | None:
    return maybe_workspace_tool_response_adapter(
        text,
        conversation_id=conversation_id,
        client_session_id=client_session_id,
        agent_access_mode=agent_access_mode,
        ToolChatResponse=ToolChatResponse,
        maybe_plan_workspace_request=maybe_plan_workspace_request,
        execute_workspace_plan=_execute_workspace_plan,
        maybe_workspace_tool_response_impl=maybe_workspace_tool_response_impl,
    )
def _maybe_research_tool_response(text: str, *, conversation_id: int | None) -> ToolChatResponse | None:
    return maybe_research_tool_response_adapter(
        text,
        conversation_id=conversation_id,
        ToolChatResponse=ToolChatResponse,
        maybe_plan_research_request=maybe_plan_research_request,
        execute_research_plan=_execute_research_plan,
        maybe_research_tool_response_impl=maybe_research_tool_response_impl,
    )
def _execute_calendar_plan(plan: CalendarPlan, *, raw_message: str, conversation_id: int | None) -> str:
    return execute_calendar_plan_adapter(
        plan,
        raw_message=raw_message,
        conversation_id=conversation_id,
        execute_calendar_plan_impl=execute_calendar_plan_impl,
        begin_google_calendar_auth=begin_google_calendar_auth,
        calendar_lookup_reply=_calendar_lookup_reply,
        extract_calendar_create_text=_extract_calendar_create_text,
        calendar_create_reply=_calendar_create_reply,
        calendar_details_reply=_calendar_details_reply,
        calendar_delete_request_reply=_calendar_delete_request_reply,
        calendar_update_request_reply=_calendar_update_request_reply,
        calendar_move_request_reply=_calendar_move_request_reply,
    )
def _execute_workspace_plan(
    plan,
    *,
    conversation_id: int | None,
    client_session_id: str | None,
    agent_access_mode: str | None,
) -> ToolChatResponse:
    return execute_workspace_plan_impl(
        plan,
        conversation_id=conversation_id,
        client_session_id=client_session_id,
        agent_access_mode=agent_access_mode,
        ToolChatResponse=ToolChatResponse,
        cfg=cfg,
        clean_query=_clean_query,
        repo_search_reply=_repo_search_reply,
        remember_workspace_context=remember_workspace_context,
        read_file_reply=_read_file_reply,
        list_reply=_list_reply,
        guard_command_tool_response=_guard_command_tool_response,
    )
def _execute_research_plan(plan, *, conversation_id: int | None) -> str:
    return execute_research_plan_adapter(
        plan,
        conversation_id=conversation_id,
        execute_research_plan_impl=execute_research_plan_impl,
        clean_query=_clean_query,
        google_search_reply=_google_search_reply,
        web_search_reply=_web_search_reply,
        remember_research_context=remember_research_context,
    )

