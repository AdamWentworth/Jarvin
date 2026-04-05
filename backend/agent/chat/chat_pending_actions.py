from __future__ import annotations


def maybe_handle_pending_confirmation_impl(
    text: str,
    *,
    conversation_id,
    ToolChatResponse,
    get_pending_host_approval,
    normalize_confirmation_text,
    cancel_patterns,
    confirm_patterns,
    update_latest_tool_turn,
    build_approval_payload,
    clear_pending_host_approval,
    execute_pending_host_approval,
    get_pending_calendar_action,
    clear_pending_calendar_action,
    delete_calendar_event,
    reschedule_calendar_event,
    update_calendar_event_fields,
    calendar_field_update_success_reply,
):
    host_pending = get_pending_host_approval(conversation_id)
    if host_pending is not None:
        normalized = normalize_confirmation_text(text)
        if normalized in cancel_patterns:
            update_latest_tool_turn(
                conversation_id=conversation_id,
                tool_kind="approval_request",
                tool_payload=build_approval_payload(
                    host_pending,
                    access_mode="approve_risky",
                    status="denied",
                    can_approve=False,
                ),
            )
            clear_pending_host_approval(conversation_id)
            return ToolChatResponse(handled=True, reply="Okay, I canceled that pending host action.", active_domain="workspace")

        if normalized in confirm_patterns or normalized == "approve":
            update_latest_tool_turn(
                conversation_id=conversation_id,
                tool_kind="approval_request",
                tool_payload=build_approval_payload(
                    host_pending,
                    access_mode="approve_risky",
                    status="approved",
                    can_approve=False,
                ),
            )
            clear_pending_host_approval(conversation_id)
            return execute_pending_host_approval(host_pending, conversation_id=conversation_id)

    pending = get_pending_calendar_action(conversation_id)
    if pending is None:
        return ToolChatResponse(handled=False)

    normalized = normalize_confirmation_text(text)
    if normalized in cancel_patterns:
        clear_pending_calendar_action(conversation_id)
        return ToolChatResponse(handled=True, reply="Okay, I canceled that pending calendar change.")

    if normalized not in confirm_patterns:
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
            reply=calendar_field_update_success_reply(updated, pending),
            active_domain="calendar",
        )

    return ToolChatResponse(handled=False)


def execute_pending_host_approval_impl(
    pending,
    *,
    conversation_id,
    ToolChatResponse,
    clean_query,
    run_reply,
    remember_workspace_context,
    tools,
):
    if pending.action == "run_command":
        command = clean_query(pending.command or "")
        if not command:
            raise ValueError("That pending command approval is missing the command text.")
        reply = run_reply(command)
        remember_workspace_context(conversation_id, action="run_command", command=command)
        return ToolChatResponse(handled=True, reply=reply, active_domain="workspace")

    if pending.action == "write_file":
        path = clean_query(pending.path or "")
        if not path:
            raise ValueError("That pending file approval is missing the target path.")
        content = pending.content or ""
        result = tools.write_file(path, content, append=pending.append)
        remember_workspace_context(conversation_id, action="write_file", path=result.path)
        action = "Appended to" if result.append else "Wrote"
        return ToolChatResponse(
            handled=True,
            reply=f"{action} `{result.path}` ({result.bytes_written} bytes).",
            active_domain="workspace",
        )

    raise ValueError(f"Unsupported pending host approval `{pending.action}`.")


def guard_command_tool_response_impl(
    command: str,
    *,
    conversation_id,
    agent_access_mode,
    ToolChatResponse,
    clean_query,
    normalize_agent_access_mode,
    run_reply,
    remember_workspace_context,
    PendingHostApproval,
    set_pending_host_approval,
    build_approval_payload,
):
    cleaned = clean_query(command or "")
    if not cleaned:
        return ToolChatResponse(handled=True, reply="Tell me which safe command to run.", active_domain="workspace")

    access_mode = normalize_agent_access_mode(agent_access_mode)
    if access_mode == "full_access":
        try:
            reply = run_reply(cleaned)
            remember_workspace_context(conversation_id, action="run_command", command=cleaned)
            return ToolChatResponse(handled=True, reply=reply, active_domain="workspace")
        except Exception as exc:
            detail = str(exc).strip()
            return ToolChatResponse(
                handled=True,
                reply=f"I couldn't run that command. {detail}".strip(),
                active_domain="workspace",
            )

    pending = PendingHostApproval(
        action="run_command",
        title="Run host command",
        summary=f"Run `{cleaned}` on the Jarvin host.",
        risk_level="medium",
        command=cleaned,
    )
    if access_mode == "approve_risky":
        set_pending_host_approval(conversation_id, pending)
        return ToolChatResponse(
            handled=True,
            reply=(
                f"I’m ready to run `{cleaned}` on the Jarvin host. "
                "Approve or deny it from the action card below, or reply `approve` / `deny`."
            ),
            tool_kind="approval_request",
            tool_payload=build_approval_payload(
                pending,
                access_mode=access_mode,
                status="pending",
                can_approve=True,
            ),
            active_domain="workspace",
        )

    return ToolChatResponse(
        handled=True,
        reply=(
            f"`{cleaned}` needs host command access, and this client is currently in read-only mode. "
            "Switch Agent access to `Approve risky actions` or `Trusted full access` in Settings to continue."
        ),
        tool_kind="approval_request",
        tool_payload=build_approval_payload(
            pending,
            access_mode=access_mode,
            status="blocked",
            can_approve=False,
        ),
        active_domain="workspace",
    )


def guard_write_tool_command_impl(
    rest: str,
    *,
    append: bool,
    conversation_id,
    agent_access_mode,
    ToolChatResponse,
    parse_write_args,
    normalize_agent_access_mode,
    tools,
    remember_workspace_context,
    PendingHostApproval,
    set_pending_host_approval,
    build_approval_payload,
):
    try:
        path, content = parse_write_args(rest)
    except Exception as exc:
        detail = str(exc).strip()
        return ToolChatResponse(
            handled=True,
            reply=f"I couldn't prepare that file write. {detail}".strip(),
            active_domain="workspace",
        )

    access_mode = normalize_agent_access_mode(agent_access_mode)
    if access_mode == "full_access":
        try:
            result = tools.write_file(path, content, append=append)
            remember_workspace_context(conversation_id, action="write_file", path=result.path)
            action = "Appended to" if result.append else "Wrote"
            return ToolChatResponse(
                handled=True,
                reply=f"{action} `{result.path}` ({result.bytes_written} bytes).",
                active_domain="workspace",
            )
        except Exception as exc:
            detail = str(exc).strip()
            return ToolChatResponse(
                handled=True,
                reply=f"I couldn't write that file. {detail}".strip(),
                active_domain="workspace",
            )

    pending = PendingHostApproval(
        action="write_file",
        title="Write file on host",
        summary=f"{'Append to' if append else 'Write'} `{path}` in the Jarvin workspace.",
        risk_level="high",
        path=path,
        content=content,
        append=append,
    )
    if access_mode == "approve_risky":
        set_pending_host_approval(conversation_id, pending)
        return ToolChatResponse(
            handled=True,
            reply=(
                f"I’m ready to {'append to' if append else 'write'} `{path}` on the Jarvin host. "
                "Approve or deny it from the action card below, or reply `approve` / `deny`."
            ),
            tool_kind="approval_request",
            tool_payload=build_approval_payload(
                pending,
                access_mode=access_mode,
                status="pending",
                can_approve=True,
            ),
            active_domain="workspace",
        )

    return ToolChatResponse(
        handled=True,
        reply=(
            f"Writing `{path}` needs workspace write access, and this client is currently in read-only mode. "
            "Switch Agent access to `Approve risky actions` or `Trusted full access` in Settings to continue."
        ),
        tool_kind="approval_request",
        tool_payload=build_approval_payload(
            pending,
            access_mode=access_mode,
            status="blocked",
            can_approve=False,
        ),
        active_domain="workspace",
    )
