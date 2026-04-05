from __future__ import annotations


def maybe_handle_pending_confirmation_impl(
    text: str,
    *,
    conversation_id,
    client_session_id,
    ToolChatResponse,
    get_pending_host_approval,
    normalize_confirmation_text,
    cancel_patterns,
    confirm_patterns,
    trust_conversation_patterns,
    trust_session_patterns,
    update_latest_tool_turn,
    build_approval_payload,
    clear_pending_host_approval,
    grant_host_action_trust,
    execute_pending_host_approval,
    log_agent_action_event,
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
            log_agent_action_event(
                conversation_id=conversation_id,
                event_kind="denied",
                action_kind=host_pending.action,
                risk_level=host_pending.risk_level,
                access_mode="approve_risky",
                title=host_pending.title,
                summary=host_pending.summary,
                command=host_pending.command,
                path=host_pending.path,
                content_preview=host_pending.content,
                detail="User denied the pending host action.",
            )
            update_latest_tool_turn(
                conversation_id=conversation_id,
                tool_kind="approval_request",
                tool_payload=build_approval_payload(
                    host_pending,
                    access_mode="approve_risky",
                    status="denied",
                    can_approve=False,
                    can_trust_conversation=False,
                ),
            )
            clear_pending_host_approval(conversation_id)
            return ToolChatResponse(
                handled=True,
                reply="Okay, I canceled that pending host action.",
                active_domain="workspace",
            )

        if normalized in trust_conversation_patterns:
            grant = grant_host_action_trust(
                conversation_id,
                client_session_id,
                host_pending.action,
                scope="conversation",
            )
            log_agent_action_event(
                conversation_id=conversation_id,
                event_kind="trusted",
                action_kind=host_pending.action,
                risk_level=host_pending.risk_level,
                access_mode="approve_risky",
                title=host_pending.title,
                summary=host_pending.summary,
                command=host_pending.command,
                path=host_pending.path,
                content_preview=host_pending.content,
                client_session_id=client_session_id,
                trust_scope=grant.scope,
                detail=f"Trusted similar `{host_pending.action}` actions in this conversation until {grant.expires_at.isoformat()}.",
            )
            update_latest_tool_turn(
                conversation_id=conversation_id,
                tool_kind="approval_request",
                tool_payload=build_approval_payload(
                    host_pending,
                    access_mode="approve_risky",
                    status="trusted",
                    can_approve=False,
                    can_trust_conversation=False,
                    can_trust_session=False,
                    trust_active=True,
                    trust_scope=grant.scope,
                ),
            )
            clear_pending_host_approval(conversation_id)
            return execute_pending_host_approval(
                host_pending,
                conversation_id=conversation_id,
                client_session_id=client_session_id,
            )

        if normalized in trust_session_patterns:
            grant = grant_host_action_trust(
                conversation_id,
                client_session_id,
                host_pending.action,
                scope="session",
            )
            log_agent_action_event(
                conversation_id=conversation_id,
                event_kind="trusted",
                action_kind=host_pending.action,
                risk_level=host_pending.risk_level,
                access_mode="approve_risky",
                title=host_pending.title,
                summary=host_pending.summary,
                command=host_pending.command,
                path=host_pending.path,
                content_preview=host_pending.content,
                client_session_id=client_session_id,
                trust_scope=grant.scope,
                detail=f"Trusted similar `{host_pending.action}` actions for this client session until {grant.expires_at.isoformat()}.",
            )
            update_latest_tool_turn(
                conversation_id=conversation_id,
                tool_kind="approval_request",
                tool_payload=build_approval_payload(
                    host_pending,
                    access_mode="approve_risky",
                    status="trusted",
                    can_approve=False,
                    can_trust_conversation=False,
                    can_trust_session=False,
                    trust_active=True,
                    trust_scope=grant.scope,
                ),
            )
            clear_pending_host_approval(conversation_id)
            return execute_pending_host_approval(
                host_pending,
                conversation_id=conversation_id,
                client_session_id=client_session_id,
            )

        if normalized in confirm_patterns or normalized == "approve":
            log_agent_action_event(
                conversation_id=conversation_id,
                event_kind="approved",
                action_kind=host_pending.action,
                risk_level=host_pending.risk_level,
                access_mode="approve_risky",
                title=host_pending.title,
                summary=host_pending.summary,
                command=host_pending.command,
                path=host_pending.path,
                content_preview=host_pending.content,
                client_session_id=client_session_id,
                detail="User approved the pending host action once.",
            )
            update_latest_tool_turn(
                conversation_id=conversation_id,
                tool_kind="approval_request",
                tool_payload=build_approval_payload(
                    host_pending,
                    access_mode="approve_risky",
                    status="approved",
                    can_approve=False,
                    can_trust_conversation=False,
                    can_trust_session=False,
                ),
            )
            clear_pending_host_approval(conversation_id)
            return execute_pending_host_approval(
                host_pending,
                conversation_id=conversation_id,
                client_session_id=client_session_id,
            )

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
