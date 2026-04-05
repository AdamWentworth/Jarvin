from __future__ import annotations


def maybe_host_task_response_impl(
    text: str,
    *,
    conversation_id,
    client_session_id,
    agent_access_mode,
    ToolChatResponse,
    normalize_agent_access_mode,
    maybe_plan_host_task_request,
    build_pending_host_task,
    set_pending_host_task,
    get_running_host_task,
    build_host_task_payload,
    log_agent_action_event,
):
    running = get_running_host_task(conversation_id)
    if running is not None:
        return ToolChatResponse(
            handled=True,
            reply=(
                f"I already have `{running.title}` running in this conversation. "
                "Let that finish or deny it before starting another host task."
            ),
            active_domain="workspace",
        )

    planned = maybe_plan_host_task_request(text, conversation_id=conversation_id)
    if planned is None or not planned.is_task_request or not planned.steps:
        return None

    access_mode = normalize_agent_access_mode(agent_access_mode)
    pending = build_pending_host_task(planned, conversation_id=conversation_id)
    has_command_step = any(step.action_kind == "run_command" for step in pending.steps)
    has_write_step = any(step.action_kind == "write_file" for step in pending.steps)
    details = [
        f"{len(pending.steps)} planned step(s).",
        "This task approval only covers the listed steps.",
    ]
    if has_write_step:
        details.append("This task includes planned file edits on the host workspace.")

    if access_mode == "read_only" and (has_command_step or has_write_step):
        log_agent_action_event(
            conversation_id=conversation_id,
            event_kind="blocked",
            action_kind="host_task",
            risk_level=pending.risk_level,
            access_mode=access_mode,
            title=pending.title,
            summary=pending.summary,
            client_session_id=client_session_id,
            detail="Task includes risky host steps while this client is in read-only mode.",
        )
        return ToolChatResponse(
            handled=True,
            reply=(
                f"I planned `{pending.title}`, but it includes risky host steps and this client is currently in read-only mode. "
                "Switch Agent access to `Approve risky actions` or `Trusted host tool access` to run it."
            ),
            tool_kind="task_request",
            tool_payload=build_host_task_payload(
                pending,
                access_mode=access_mode,
                status="blocked",
                can_approve=False,
                details=details,
            ),
            active_domain="workspace",
        )

    set_pending_host_task(conversation_id, pending)
    log_agent_action_event(
        conversation_id=conversation_id,
        event_kind="requested",
        action_kind="host_task",
        risk_level=pending.risk_level,
        access_mode=access_mode,
        title=pending.title,
        summary=pending.summary,
        client_session_id=client_session_id,
        detail="Waiting for one task approval before executing the planned steps.",
    )
    return ToolChatResponse(
        handled=True,
        reply=(
            f"I can tackle that as `{pending.title}`. "
            f"Review the {len(pending.steps)} planned step(s) below and approve the task when you're ready."
        ),
        tool_kind="task_request",
        tool_payload=build_host_task_payload(
            pending,
            access_mode=access_mode,
            status="pending",
            can_approve=True,
            details=details,
        ),
        active_domain="workspace",
    )
