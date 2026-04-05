from __future__ import annotations


def maybe_active_follow_up_response_impl(
    text: str,
    *,
    conversation_id,
    client_session_id,
    agent_access_mode,
    get_active_follow_up_domain,
    looks_like_ambiguous_follow_up,
    has_conflicting_domain_cues,
    dispatch_active_follow_up,
):
    active_domain = get_active_follow_up_domain(conversation_id)
    if active_domain is None:
        return None
    if not looks_like_ambiguous_follow_up(text):
        return None
    if has_conflicting_domain_cues(text, active_domain=active_domain):
        return None
    return dispatch_active_follow_up(
        active_domain,
        text,
        conversation_id=conversation_id,
        client_session_id=client_session_id,
        agent_access_mode=agent_access_mode,
    )


def dispatch_active_follow_up_impl(
    active_domain: str,
    text: str,
    *,
    conversation_id,
    client_session_id,
    agent_access_mode,
    maybe_weather_tool_response,
    maybe_handle_brief_request,
    maybe_handle_reminder_request,
    maybe_calendar_tool_response,
    maybe_workspace_tool_response,
    maybe_research_tool_response,
    ToolChatResponse,
):
    if active_domain == "weather":
        return maybe_weather_tool_response(text, conversation_id=conversation_id)
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
        return maybe_calendar_tool_response(text, conversation_id=conversation_id)
    if active_domain == "workspace":
        return maybe_workspace_tool_response(
            text,
            conversation_id=conversation_id,
            client_session_id=client_session_id,
            agent_access_mode=agent_access_mode,
        )
    if active_domain == "research":
        return maybe_research_tool_response(text, conversation_id=conversation_id)
    return None


def safe_weather_tool_response_impl(
    rest: str,
    *,
    conversation_id,
    ToolChatResponse,
    maybe_handle_weather_request,
):
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


def maybe_weather_tool_response_impl(
    text: str,
    *,
    conversation_id,
    ToolChatResponse,
    maybe_handle_weather_request,
):
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


def maybe_calendar_tool_response_impl(
    text: str,
    *,
    conversation_id,
    ToolChatResponse,
    maybe_plan_calendar_request,
    execute_calendar_plan,
):
    plan = maybe_plan_calendar_request(text, conversation_id=conversation_id)
    if plan is None:
        return None
    try:
        return ToolChatResponse(
            handled=True,
            reply=execute_calendar_plan(plan, raw_message=text, conversation_id=conversation_id),
            active_domain="calendar",
        )
    except Exception as exc:
        detail = str(exc).strip()
        return ToolChatResponse(
            handled=True,
            reply=f"I couldn't work with your calendar just now. {detail}".strip(),
            active_domain="calendar",
        )


def maybe_workspace_tool_response_impl(
    text: str,
    *,
    conversation_id,
    client_session_id,
    agent_access_mode,
    ToolChatResponse,
    maybe_plan_workspace_request,
    execute_workspace_plan,
):
    plan = maybe_plan_workspace_request(text, conversation_id=conversation_id)
    if plan is None or plan.action == "unknown":
        return None
    try:
        return execute_workspace_plan(
            plan,
            conversation_id=conversation_id,
            client_session_id=client_session_id,
            agent_access_mode=agent_access_mode,
        )
    except Exception as exc:
        detail = str(exc).strip()
        return ToolChatResponse(
            handled=True,
            reply=f"I couldn't work with the local workspace just now. {detail}".strip(),
            active_domain="workspace",
        )


def maybe_research_tool_response_impl(
    text: str,
    *,
    conversation_id,
    ToolChatResponse,
    maybe_plan_research_request,
    execute_research_plan,
):
    plan = maybe_plan_research_request(text, conversation_id=conversation_id)
    if plan is None or plan.action == "unknown":
        return None
    try:
        return ToolChatResponse(
            handled=True,
            reply=execute_research_plan(plan, conversation_id=conversation_id),
            active_domain="research",
        )
    except Exception as exc:
        detail = str(exc).strip()
        return ToolChatResponse(
            handled=True,
            reply=f"I couldn't search the web just now. {detail}".strip(),
            active_domain="research",
        )


def execute_calendar_plan_impl(plan, *, raw_message: str, conversation_id, begin_google_calendar_auth, calendar_lookup_reply, extract_calendar_create_text, calendar_create_reply, calendar_details_reply, calendar_delete_request_reply, calendar_update_request_reply, calendar_move_request_reply):
    action = (plan.action or "lookup").strip().lower()

    if action == "auth":
        return begin_google_calendar_auth()

    if action == "lookup":
        return calendar_lookup_reply(raw_message, window_days_override=plan.window_days)

    if action == "create":
        details = plan.query or extract_calendar_create_text(raw_message)
        if not details:
            raise ValueError("Tell me what event to create and when it should happen.")
        return calendar_create_reply(details)

    if action == "details":
        query = plan.query or raw_message
        return calendar_details_reply(query)

    if action == "delete":
        query = plan.query or raw_message
        return calendar_delete_request_reply(query, conversation_id=conversation_id)

    if action == "rename":
        query = plan.query or raw_message
        if not plan.new_title:
            raise ValueError("Tell me the new event title too.")
        return calendar_update_request_reply(query, conversation_id=conversation_id, title=plan.new_title)

    if action == "update_location":
        query = plan.query or raw_message
        if plan.new_location is None:
            raise ValueError("Tell me the new event location too.")
        return calendar_update_request_reply(query, conversation_id=conversation_id, location=plan.new_location)

    if action == "update_description":
        query = plan.query or raw_message
        if plan.new_description is None:
            raise ValueError("Tell me the new event notes too.")
        return calendar_update_request_reply(query, conversation_id=conversation_id, description=plan.new_description)

    if action == "move":
        query = plan.query or raw_message
        when_text = plan.when_text or raw_message
        return calendar_move_request_reply(query, when_text, conversation_id=conversation_id)

    return calendar_lookup_reply(raw_message, window_days_override=plan.window_days)


def execute_workspace_plan_impl(
    plan,
    *,
    conversation_id,
    client_session_id,
    agent_access_mode,
    ToolChatResponse,
    cfg,
    clean_query,
    repo_search_reply,
    remember_workspace_context,
    read_file_reply,
    list_reply,
    guard_command_tool_response,
):
    action = str(plan.action or "").strip().lower()

    if action == "search_repo":
        query = clean_query(plan.query or "")
        if not query:
            raise ValueError("Tell me what to search for in the repo.")
        reply = repo_search_reply(query)
        remember_workspace_context(conversation_id, action="search_repo", query=query)
        return ToolChatResponse(handled=True, reply=reply, active_domain="workspace")

    if action == "read_file":
        path = clean_query(plan.path or "")
        if not path:
            raise ValueError("Tell me which file to read.")
        start_line = int(plan.start_line or 1)
        end_line = int(plan.end_line) if plan.end_line is not None else None
        reply = read_file_reply(path, start_line, end_line)
        inferred_end = end_line if end_line is not None else start_line + int(cfg.settings.agent_max_file_read_lines) - 1
        remember_workspace_context(
            conversation_id,
            action="read_file",
            path=path,
            start_line=start_line,
            end_line=inferred_end,
        )
        return ToolChatResponse(handled=True, reply=reply, active_domain="workspace")

    if action == "list_directory":
        path = clean_query(plan.path or ".") or "."
        reply = list_reply(path)
        remember_workspace_context(conversation_id, action="list_directory", path=path)
        return ToolChatResponse(handled=True, reply=reply, active_domain="workspace")

    if action == "run_command":
        command = clean_query(plan.command or "")
        if not command:
            raise ValueError("Tell me which safe command to run.")
        return guard_command_tool_response(
            command,
            conversation_id=conversation_id,
            client_session_id=client_session_id,
            agent_access_mode=agent_access_mode,
        )

    raise ValueError(f"Unsupported workspace action `{action}`.")


def execute_research_plan_impl(
    plan,
    *,
    conversation_id,
    clean_query,
    google_search_reply,
    web_search_reply,
    remember_research_context,
):
    action = str(plan.action or "").strip().lower()
    query = clean_query(plan.query or "")
    if not query:
        raise ValueError("Tell me what you want me to research.")

    if action == "google_search":
        reply = google_search_reply(query, natural=True)
        remember_research_context(conversation_id, action="google_search", query=query)
        return reply

    reply = web_search_reply(query)
    remember_research_context(conversation_id, action="web_search", query=query)
    return reply
