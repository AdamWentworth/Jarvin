from __future__ import annotations

from backend.agent.chat.chat_host_action_execution import (
    execute_command_immediately,
    execute_write_immediately,
)


def execute_pending_host_approval_impl(
    pending,
    *,
    conversation_id,
    client_session_id,
    ToolChatResponse,
    clean_query,
    run_reply,
    remember_workspace_context,
    tools,
    log_agent_action_event,
    access_mode,
):
    if pending.action == "run_command":
        command = clean_query(pending.command or "")
        if not command:
            raise ValueError("That pending command approval is missing the command text.")
        try:
            reply = run_reply(command)
            remember_workspace_context(conversation_id, action="run_command", command=command)
            log_agent_action_event(
                conversation_id=conversation_id,
                event_kind="executed",
                action_kind=pending.action,
                risk_level=pending.risk_level,
                access_mode=access_mode,
                title=pending.title,
                summary=pending.summary,
                command=command,
                path=pending.path,
                content_preview=pending.content,
                client_session_id=client_session_id,
                working_directory=str(tools.workspace_root()),
                argv=tools.describe_safe_command(command)["argv"],
                detail="Host command executed successfully.",
            )
            return ToolChatResponse(handled=True, reply=reply, active_domain="workspace")
        except Exception as exc:
            detail = str(exc).strip() or "Host command failed."
            log_agent_action_event(
                conversation_id=conversation_id,
                event_kind="failed",
                action_kind=pending.action,
                risk_level=pending.risk_level,
                access_mode=access_mode,
                title=pending.title,
                summary=pending.summary,
                command=command,
                path=pending.path,
                content_preview=pending.content,
                client_session_id=client_session_id,
                working_directory=str(tools.workspace_root()),
                argv=tools.describe_safe_command(command)["argv"] if command else None,
                detail=detail,
            )
            return ToolChatResponse(
                handled=True,
                reply=f"I couldn't run that command. {detail}".strip(),
                active_domain="workspace",
            )

    if pending.action == "write_file":
        path = clean_query(pending.path or "")
        if not path:
            raise ValueError("That pending file approval is missing the target path.")
        content = pending.content or ""
        try:
            result = tools.write_file(path, content, append=pending.append)
            remember_workspace_context(conversation_id, action="write_file", path=result.path)
            action = "Appended to" if result.append else "Wrote"
            log_agent_action_event(
                conversation_id=conversation_id,
                event_kind="executed",
                action_kind=pending.action,
                risk_level=pending.risk_level,
                access_mode=access_mode,
                title=pending.title,
                summary=pending.summary,
                command=pending.command,
                path=result.path,
                content_preview=content,
                client_session_id=client_session_id,
                diff_preview=tools.build_write_diff_preview(path, content, append=pending.append),
                detail=f"{action} file successfully.",
            )
            return ToolChatResponse(
                handled=True,
                reply=f"{action} `{result.path}` ({result.bytes_written} bytes).",
                active_domain="workspace",
            )
        except Exception as exc:
            detail = str(exc).strip() or "File write failed."
            log_agent_action_event(
                conversation_id=conversation_id,
                event_kind="failed",
                action_kind=pending.action,
                risk_level=pending.risk_level,
                access_mode=access_mode,
                title=pending.title,
                summary=pending.summary,
                command=pending.command,
                path=path,
                content_preview=content,
                client_session_id=client_session_id,
                diff_preview=tools.build_write_diff_preview(path, content, append=pending.append),
                detail=detail,
            )
            return ToolChatResponse(
                handled=True,
                reply=f"I couldn't write that file. {detail}".strip(),
                active_domain="workspace",
            )

    raise ValueError(f"Unsupported pending host approval `{pending.action}`.")


def guard_command_tool_response_impl(
    command: str,
    *,
    conversation_id,
    client_session_id,
    agent_access_mode,
    ToolChatResponse,
    clean_query,
    normalize_agent_access_mode,
    run_reply,
    remember_workspace_context,
    tools,
    PendingHostApproval,
    set_pending_host_approval,
    build_approval_payload,
    get_host_action_trust,
    log_agent_action_event,
):
    cleaned = clean_query(command or "")
    if not cleaned:
        return ToolChatResponse(handled=True, reply="Tell me which safe command to run.", active_domain="workspace")

    try:
        command_info = tools.describe_safe_command(cleaned)
    except Exception as exc:
        detail = str(exc).strip()
        return ToolChatResponse(
            handled=True,
            reply=f"I couldn't prepare that host command. {detail}".strip(),
            active_domain="workspace",
        )
    access_mode = normalize_agent_access_mode(agent_access_mode)
    base_summary = f"Run `{cleaned}` on the Jarvin host."
    if access_mode == "full_access":
        return execute_command_immediately(
            cleaned,
            conversation_id=conversation_id,
            client_session_id=client_session_id,
            ToolChatResponse=ToolChatResponse,
            run_reply=run_reply,
            remember_workspace_context=remember_workspace_context,
            log_agent_action_event=log_agent_action_event,
            access_mode=access_mode,
            detail="Executed immediately under trusted host tool access.",
            working_directory=str(command_info["working_directory"]),
            argv=command_info["argv"],
        )

    trust = (
        get_host_action_trust(conversation_id, client_session_id, "run_command")
        if access_mode == "approve_risky"
        else None
    )
    if trust is not None:
        return execute_command_immediately(
            cleaned,
            conversation_id=conversation_id,
            client_session_id=client_session_id,
            ToolChatResponse=ToolChatResponse,
            run_reply=run_reply,
            remember_workspace_context=remember_workspace_context,
            log_agent_action_event=log_agent_action_event,
            access_mode=access_mode,
            detail=f"Executed under {trust.scope} trust until {trust.expires_at.isoformat()}.",
            working_directory=str(command_info["working_directory"]),
            argv=command_info["argv"],
        )

    pending = PendingHostApproval(
        action="run_command",
        title="Run host command",
        summary=base_summary,
        risk_level="medium",
        command=cleaned,
    )
    if access_mode == "approve_risky":
        set_pending_host_approval(conversation_id, pending)
        log_agent_action_event(
            conversation_id=conversation_id,
            event_kind="requested",
            action_kind=pending.action,
            risk_level=pending.risk_level,
            access_mode=access_mode,
            title=pending.title,
            summary=pending.summary,
            command=pending.command,
            client_session_id=client_session_id,
            working_directory=str(command_info["working_directory"]),
            argv=command_info["argv"],
            detail="Waiting for approval or trust in this conversation.",
        )
        return ToolChatResponse(
            handled=True,
            reply=(
                f"I'm ready to run `{cleaned}` on the Jarvin host. "
                "Approve it once, trust similar commands in this chat or this session, or deny it from the action card below."
            ),
            tool_kind="approval_request",
            tool_payload=build_approval_payload(
                pending,
                access_mode=access_mode,
                status="pending",
                can_approve=True,
                can_trust_conversation=True,
                can_trust_session=True,
                extra_details=[
                    f"Working directory: {command_info['working_directory']}",
                    f"Arguments: {' | '.join(command_info['argv'])}",
                ],
                preview_block="\n".join(command_info["argv"]),
            ),
            active_domain="workspace",
        )

    log_agent_action_event(
        conversation_id=conversation_id,
        event_kind="blocked",
        action_kind=pending.action,
        risk_level=pending.risk_level,
        access_mode=access_mode,
        title=pending.title,
        summary=pending.summary,
        command=pending.command,
        client_session_id=client_session_id,
        working_directory=str(command_info["working_directory"]),
        argv=command_info["argv"],
        detail="Client is in read-only mode.",
    )
    return ToolChatResponse(
        handled=True,
        reply=(
            f"`{cleaned}` needs host command access, and this client is currently in read-only mode. "
            "Switch Agent access to `Approve risky actions` or `Trusted host tool access` in Settings to continue."
        ),
        tool_kind="approval_request",
        tool_payload=build_approval_payload(
            pending,
            access_mode=access_mode,
            status="blocked",
            can_approve=False,
            can_trust_conversation=False,
            can_trust_session=False,
            extra_details=[
                f"Working directory: {command_info['working_directory']}",
                f"Arguments: {' | '.join(command_info['argv'])}",
            ],
            preview_block="\n".join(command_info["argv"]),
        ),
        active_domain="workspace",
    )


def guard_write_tool_command_impl(
    rest: str,
    *,
    append: bool,
    conversation_id,
    client_session_id,
    agent_access_mode,
    ToolChatResponse,
    parse_write_args,
    normalize_agent_access_mode,
    tools,
    remember_workspace_context,
    PendingHostApproval,
    set_pending_host_approval,
    build_approval_payload,
    get_host_action_trust,
    log_agent_action_event,
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
    base_summary = f"{'Append to' if append else 'Write'} `{path}` in the Jarvin workspace."
    try:
        diff_preview = tools.build_write_diff_preview(path, content, append=append)
    except Exception as exc:
        detail = str(exc).strip()
        return ToolChatResponse(
            handled=True,
            reply=f"I couldn't prepare that file write. {detail}".strip(),
            active_domain="workspace",
        )
    if access_mode == "full_access":
        return execute_write_immediately(
            path,
            content,
            append=append,
            conversation_id=conversation_id,
            client_session_id=client_session_id,
            ToolChatResponse=ToolChatResponse,
            tools=tools,
            remember_workspace_context=remember_workspace_context,
            log_agent_action_event=log_agent_action_event,
            access_mode=access_mode,
            detail="Executed immediately under trusted host tool access.",
            diff_preview=diff_preview,
        )

    trust = (
        get_host_action_trust(conversation_id, client_session_id, "write_file")
        if access_mode == "approve_risky"
        else None
    )
    if trust is not None:
        return execute_write_immediately(
            path,
            content,
            append=append,
            conversation_id=conversation_id,
            client_session_id=client_session_id,
            ToolChatResponse=ToolChatResponse,
            tools=tools,
            remember_workspace_context=remember_workspace_context,
            log_agent_action_event=log_agent_action_event,
            access_mode=access_mode,
            detail=f"Executed under {trust.scope} trust until {trust.expires_at.isoformat()}.",
            diff_preview=diff_preview,
        )

    pending = PendingHostApproval(
        action="write_file",
        title="Write file on host",
        summary=base_summary,
        risk_level="high",
        path=path,
        content=content,
        append=append,
    )
    if access_mode == "approve_risky":
        set_pending_host_approval(conversation_id, pending)
        log_agent_action_event(
            conversation_id=conversation_id,
            event_kind="requested",
            action_kind=pending.action,
            risk_level=pending.risk_level,
            access_mode=access_mode,
            title=pending.title,
            summary=pending.summary,
            path=pending.path,
            content_preview=pending.content,
            client_session_id=client_session_id,
            diff_preview=diff_preview,
            detail="Waiting for approval or trust in this conversation.",
        )
        return ToolChatResponse(
            handled=True,
            reply=(
                f"I'm ready to {'append to' if append else 'write'} `{path}` on the Jarvin host. "
                "Approve it once, trust similar writes in this chat or this session, or deny it from the action card below."
            ),
            tool_kind="approval_request",
            tool_payload=build_approval_payload(
                pending,
                access_mode=access_mode,
                status="pending",
                can_approve=True,
                can_trust_conversation=True,
                can_trust_session=True,
                extra_details=[f"Working directory: {tools.workspace_root()}"],
                preview_block=diff_preview,
            ),
            active_domain="workspace",
        )

    log_agent_action_event(
        conversation_id=conversation_id,
        event_kind="blocked",
        action_kind=pending.action,
        risk_level=pending.risk_level,
        access_mode=access_mode,
        title=pending.title,
        summary=pending.summary,
        path=pending.path,
        content_preview=pending.content,
        client_session_id=client_session_id,
        diff_preview=diff_preview,
        detail="Client is in read-only mode.",
    )
    return ToolChatResponse(
        handled=True,
        reply=(
            f"Writing `{path}` needs workspace write access, and this client is currently in read-only mode. "
            "Switch Agent access to `Approve risky actions` or `Trusted host tool access` in Settings to continue."
        ),
        tool_kind="approval_request",
        tool_payload=build_approval_payload(
            pending,
            access_mode=access_mode,
            status="blocked",
            can_approve=False,
            can_trust_conversation=False,
            can_trust_session=False,
            extra_details=[f"Working directory: {tools.workspace_root()}"],
            preview_block=diff_preview,
        ),
        active_domain="workspace",
    )
