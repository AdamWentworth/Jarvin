from __future__ import annotations


def execute_calendar_plan_adapter(
    plan,
    *,
    raw_message: str,
    conversation_id,
    execute_calendar_plan_impl,
    begin_google_calendar_auth,
    calendar_lookup_reply,
    extract_calendar_create_text,
    calendar_create_reply,
    calendar_details_reply,
    calendar_delete_request_reply,
    calendar_update_request_reply,
    calendar_move_request_reply,
):
    return execute_calendar_plan_impl(
        plan,
        raw_message=raw_message,
        conversation_id=conversation_id,
        begin_google_calendar_auth=begin_google_calendar_auth,
        calendar_lookup_reply=calendar_lookup_reply,
        extract_calendar_create_text=extract_calendar_create_text,
        calendar_create_reply=calendar_create_reply,
        calendar_details_reply=calendar_details_reply,
        calendar_delete_request_reply=calendar_delete_request_reply,
        calendar_update_request_reply=calendar_update_request_reply,
        calendar_move_request_reply=calendar_move_request_reply,
    )


def maybe_calendar_tool_response_adapter(
    text: str,
    *,
    conversation_id,
    ToolChatResponse,
    maybe_plan_calendar_request,
    execute_calendar_plan,
    maybe_calendar_tool_response_impl,
):
    return maybe_calendar_tool_response_impl(
        text,
        conversation_id=conversation_id,
        ToolChatResponse=ToolChatResponse,
        maybe_plan_calendar_request=maybe_plan_calendar_request,
        execute_calendar_plan=execute_calendar_plan,
    )


def maybe_workspace_tool_response_adapter(
    text: str,
    *,
    conversation_id,
    client_session_id,
    agent_access_mode,
    ToolChatResponse,
    maybe_plan_workspace_request,
    execute_workspace_plan,
    maybe_workspace_tool_response_impl,
):
    return maybe_workspace_tool_response_impl(
        text,
        conversation_id=conversation_id,
        client_session_id=client_session_id,
        agent_access_mode=agent_access_mode,
        ToolChatResponse=ToolChatResponse,
        maybe_plan_workspace_request=maybe_plan_workspace_request,
        execute_workspace_plan=execute_workspace_plan,
    )


def maybe_research_tool_response_adapter(
    text: str,
    *,
    conversation_id,
    ToolChatResponse,
    maybe_plan_research_request,
    execute_research_plan,
    maybe_research_tool_response_impl,
):
    return maybe_research_tool_response_impl(
        text,
        conversation_id=conversation_id,
        ToolChatResponse=ToolChatResponse,
        maybe_plan_research_request=maybe_plan_research_request,
        execute_research_plan=execute_research_plan,
    )


def execute_research_plan_adapter(
    plan,
    *,
    conversation_id,
    execute_research_plan_impl,
    clean_query,
    google_search_reply,
    web_search_reply,
    remember_research_context,
):
    return execute_research_plan_impl(
        plan,
        conversation_id=conversation_id,
        clean_query=clean_query,
        google_search_reply=google_search_reply,
        web_search_reply=web_search_reply,
        remember_research_context=remember_research_context,
    )
