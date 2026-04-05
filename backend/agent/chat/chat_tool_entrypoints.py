from __future__ import annotations


def maybe_handle_tool_command_impl(
    text: str,
    *,
    conversation_id,
    agent_access_mode,
    ToolChatResponse,
    tools,
    list_reply,
    repo_search_reply,
    read_reply,
    guard_write_tool_command,
    guard_command_tool_response,
    web_search_reply,
    google_search_reply,
    safe_weather_tool_response,
    handle_brief_command,
    handle_reminder_command,
    calendar_command_reply,
):
    message = (text or "").strip()
    if not message.lower().startswith("/tool"):
        return ToolChatResponse(handled=False)

    body = message[5:].strip()
    if not body or body.lower() == "help":
        return ToolChatResponse(handled=True, reply=help_reply(tools))

    verb, _, rest = body.partition(" ")
    verb = verb.lower().strip()
    rest = rest.strip()

    if verb in {"ls", "list"}:
        return _safe_tool_call(ToolChatResponse, lambda: list_reply(rest or "."), "I couldn't list that directory.", active_domain="workspace")
    if verb == "search":
        return _safe_tool_call(ToolChatResponse, lambda: repo_search_reply(rest), "I couldn't search the workspace.", active_domain="workspace")
    if verb == "read":
        return _safe_tool_call(ToolChatResponse, lambda: read_reply(rest), "I couldn't read that file.", active_domain="workspace")
    if verb in {"write", "append"}:
        return guard_write_tool_command(
            rest,
            append=verb == "append",
            conversation_id=conversation_id,
            agent_access_mode=agent_access_mode,
        )
    if verb == "run":
        return guard_command_tool_response(rest, conversation_id=conversation_id, agent_access_mode=agent_access_mode)
    if verb == "web":
        return _safe_tool_call(ToolChatResponse, lambda: web_search_reply(rest), "I couldn't search the web just now.", active_domain="research")
    if verb == "google":
        return _safe_tool_call(ToolChatResponse, lambda: google_search_reply(rest, natural=False), "I couldn't use Google search just now.", active_domain="research")
    if verb == "weather":
        return safe_weather_tool_response(rest, conversation_id=conversation_id)
    if verb == "brief":
        return _safe_tool_call(ToolChatResponse, lambda: handle_brief_command(rest), "I couldn't build the morning brief just now.", active_domain="brief")
    if verb == "reminder":
        return _safe_tool_call(ToolChatResponse, lambda: handle_reminder_command(rest), "I couldn't manage reminders just now.", active_domain="reminder")
    if verb == "calendar":
        return _safe_tool_call(
            ToolChatResponse,
            lambda: calendar_command_reply(rest, conversation_id=conversation_id),
            "I couldn't work with your calendar just now.",
            active_domain="calendar",
        )

    return ToolChatResponse(
        handled=True,
        reply="Unknown `/tool` command. Use `/tool help` to see the available host-side actions.",
    )


def maybe_handle_natural_language_tool_request_impl(
    text: str,
    *,
    conversation_id,
    agent_access_mode,
    ToolChatResponse,
    calendar_auth_re,
    begin_google_calendar_auth,
    maybe_active_follow_up_response,
    maybe_weather_tool_response,
    maybe_handle_brief_request,
    maybe_handle_reminder_request,
    maybe_calendar_tool_response,
    maybe_workspace_tool_response,
    maybe_research_tool_response,
    calendar_details_re,
    clean_query,
    safe_tool_call,
    calendar_details_reply,
    extract_calendar_create_text,
    calendar_create_reply,
    calendar_rename_re,
    calendar_title_re,
    calendar_update_request_reply,
    calendar_location_re,
    calendar_clear_location_re,
    calendar_notes_re,
    calendar_clear_notes_re,
    calendar_delete_re,
    calendar_delete_request_reply,
    calendar_move_re,
    calendar_move_request_reply,
    infer_calendar_window_days,
    calendar_lookup_re,
    calendar_lookup_reply,
    web_search_re,
    google_re,
    repo_search_re,
    web_search_reply,
    google_search_reply,
    repo_search_reply,
    read_file_re,
    parse_read_args,
    read_file_reply,
    list_dir_re,
    list_reply,
    run_re,
    guard_command_tool_response,
):
    message = (text or "").strip()
    if not message:
        return ToolChatResponse(handled=False)

    if calendar_auth_re.search(message):
        return safe_tool_call(
            lambda: begin_google_calendar_auth(),
            "I couldn't start Google Calendar authorization.",
            active_domain="calendar",
        )

    active_follow_up = maybe_active_follow_up_response(
        message,
        conversation_id=conversation_id,
        agent_access_mode=agent_access_mode,
    )
    if active_follow_up is not None:
        return active_follow_up

    weather_reply = maybe_weather_tool_response(message, conversation_id=conversation_id)
    if weather_reply is not None:
        return weather_reply

    brief_reply = maybe_handle_brief_request(message, conversation_id=conversation_id)
    if brief_reply is not None:
        return ToolChatResponse(handled=True, reply=brief_reply, active_domain="brief")

    reminder_reply = maybe_handle_reminder_request(message, conversation_id=conversation_id)
    if reminder_reply is not None:
        return ToolChatResponse(handled=True, reply=reminder_reply, active_domain="reminder")

    calendar_reply = maybe_calendar_tool_response(message, conversation_id=conversation_id)
    if calendar_reply is not None:
        return calendar_reply

    workspace_reply = maybe_workspace_tool_response(
        message,
        conversation_id=conversation_id,
        agent_access_mode=agent_access_mode,
    )
    if workspace_reply is not None:
        return workspace_reply

    research_reply = maybe_research_tool_response(message, conversation_id=conversation_id)
    if research_reply is not None:
        return research_reply

    details_match = calendar_details_re.search(message)
    if details_match:
        query = clean_query(details_match.group("query"))
        return safe_tool_call(lambda: calendar_details_reply(query), "I couldn't open that calendar event.", active_domain="calendar")

    calendar_create = extract_calendar_create_text(message)
    if calendar_create:
        return safe_tool_call(lambda: calendar_create_reply(calendar_create), "I couldn't create that calendar event.", active_domain="calendar")

    rename_match = calendar_rename_re.search(message) or calendar_title_re.search(message)
    if rename_match:
        query = clean_query(rename_match.group("query"))
        new_title = clean_query(rename_match.group("new_title"))
        return safe_tool_call(
            lambda: calendar_update_request_reply(query, conversation_id=conversation_id, title=new_title),
            "I couldn't update that calendar event title.",
            active_domain="calendar",
        )

    location_match = calendar_location_re.search(message)
    if location_match:
        query = clean_query(location_match.group("query"))
        location = clean_query(location_match.group("location"))
        return safe_tool_call(
            lambda: calendar_update_request_reply(query, conversation_id=conversation_id, location=location),
            "I couldn't update that calendar event location.",
            active_domain="calendar",
        )

    clear_location_match = calendar_clear_location_re.search(message)
    if clear_location_match:
        query = clean_query(clear_location_match.group("query"))
        return safe_tool_call(
            lambda: calendar_update_request_reply(query, conversation_id=conversation_id, location=""),
            "I couldn't clear that calendar event location.",
            active_domain="calendar",
        )

    notes_match = calendar_notes_re.search(message)
    if notes_match:
        query = clean_query(notes_match.group("query"))
        description = clean_query(notes_match.group("description"))
        return safe_tool_call(
            lambda: calendar_update_request_reply(query, conversation_id=conversation_id, description=description),
            "I couldn't update that calendar event description.",
            active_domain="calendar",
        )

    clear_notes_match = calendar_clear_notes_re.search(message)
    if clear_notes_match:
        query = clean_query(clear_notes_match.group("query"))
        return safe_tool_call(
            lambda: calendar_update_request_reply(query, conversation_id=conversation_id, description=""),
            "I couldn't clear that calendar event description.",
            active_domain="calendar",
        )

    delete_match = calendar_delete_re.search(message)
    if delete_match:
        query = clean_query(delete_match.group("query"))
        return safe_tool_call(
            lambda: calendar_delete_request_reply(query, conversation_id=conversation_id),
            "I couldn't queue that calendar deletion.",
            active_domain="calendar",
        )

    move_match = calendar_move_re.search(message)
    if move_match:
        query = clean_query(move_match.group("query"))
        when_text = clean_query(move_match.group("when"))
        return safe_tool_call(
            lambda: calendar_move_request_reply(query, when_text, conversation_id=conversation_id),
            "I couldn't reschedule that calendar event.",
            active_domain="calendar",
        )

    days = infer_calendar_window_days(message)
    if days is not None or calendar_lookup_re.search(message):
        return safe_tool_call(
            lambda: calendar_lookup_reply(message, window_days_override=days),
            "I couldn't read your calendar right now.",
            active_domain="calendar",
        )

    web_match = web_search_re.search(message)
    if web_match:
        query = clean_query(web_match.group("query"))
        return safe_tool_call(lambda: web_search_reply(query), "I couldn't search the web just now.", active_domain="research")

    google_match = google_re.search(message)
    if google_match:
        query = clean_query(google_match.group("query"))
        return safe_tool_call(lambda: google_search_reply(query, natural=True), "I couldn't search the web just now.", active_domain="research")

    repo_match = repo_search_re.search(message)
    if repo_match:
        query = clean_query(repo_match.group("query"))
        return safe_tool_call(lambda: repo_search_reply(query), "I couldn't search the repo just now.", active_domain="workspace")

    read_match = read_file_re.search(message)
    if read_match:
        path, start_line, end_line = parse_read_args(message)
        return safe_tool_call(
            lambda: read_file_reply(path, start_line, end_line),
            "I couldn't read that file.",
            active_domain="workspace",
        )

    list_match = list_dir_re.search(message)
    if list_match:
        return safe_tool_call(lambda: list_reply(list_match.group("path")), "I couldn't list that directory.", active_domain="workspace")

    run_match = run_re.search(message)
    if run_match:
        return guard_command_tool_response(
            run_match.group("command"),
            conversation_id=conversation_id,
            agent_access_mode=agent_access_mode,
        )

    return ToolChatResponse(handled=False)


def help_reply(tools) -> str:
    manifest = tools.manifest()
    commands = "\n".join(f"- `{item}`" for item in manifest["commands"])
    allowed = "\n".join(f"- `{item}`" for item in manifest["allowed_commands"])
    return (
        "Local agent tools are available on this host.\n\n"
        f"{commands}\n\n"
        "Allowed commands:\n"
        f"{allowed}"
    )


def _safe_tool_call(ToolChatResponse, fn, fallback: str, *, active_domain: str | None = None):
    try:
        return ToolChatResponse(handled=True, reply=fn(), active_domain=active_domain)
    except Exception as exc:
        detail = str(exc).strip()
        if detail:
            return ToolChatResponse(handled=True, reply=f"{fallback} {detail}", active_domain=active_domain)
        return ToolChatResponse(handled=True, reply=fallback, active_domain=active_domain)
