from __future__ import annotations


def execute_command_immediately(
    command,
    *,
    conversation_id,
    client_session_id,
    ToolChatResponse,
    run_reply,
    remember_workspace_context,
    log_agent_action_event,
    access_mode,
    detail,
    working_directory,
    argv,
):
    try:
        reply = run_reply(command)
        remember_workspace_context(conversation_id, action="run_command", command=command)
        log_agent_action_event(
            conversation_id=conversation_id,
            event_kind="executed",
            action_kind="run_command",
            risk_level="medium",
            access_mode=access_mode,
            title="Run host command",
            summary=f"Run `{command}` on the Jarvin host.",
            command=command,
            client_session_id=client_session_id,
            working_directory=working_directory,
            argv=argv,
            detail=detail,
        )
        return ToolChatResponse(handled=True, reply=reply, active_domain="workspace")
    except Exception as exc:
        failure = str(exc).strip()
        log_agent_action_event(
            conversation_id=conversation_id,
            event_kind="failed",
            action_kind="run_command",
            risk_level="medium",
            access_mode=access_mode,
            title="Run host command",
            summary=f"Run `{command}` on the Jarvin host.",
            command=command,
            client_session_id=client_session_id,
            working_directory=working_directory,
            argv=argv,
            detail=failure,
        )
        return ToolChatResponse(
            handled=True,
            reply=f"I couldn't run that command. {failure}".strip(),
            active_domain="workspace",
        )


def execute_write_immediately(
    path,
    content,
    *,
    append,
    conversation_id,
    client_session_id,
    ToolChatResponse,
    tools,
    remember_workspace_context,
    log_agent_action_event,
    access_mode,
    detail,
    diff_preview,
):
    try:
        result = tools.write_file(path, content, append=append)
        remember_workspace_context(conversation_id, action="write_file", path=result.path)
        action = "Appended to" if result.append else "Wrote"
        log_agent_action_event(
            conversation_id=conversation_id,
            event_kind="executed",
            action_kind="write_file",
            risk_level="high",
            access_mode=access_mode,
            title="Write file on host",
            summary=f"{'Append to' if append else 'Write'} `{path}` in the Jarvin workspace.",
            path=result.path,
            content_preview=content,
            client_session_id=client_session_id,
            diff_preview=diff_preview,
            detail=detail,
        )
        return ToolChatResponse(
            handled=True,
            reply=f"{action} `{result.path}` ({result.bytes_written} bytes).",
            active_domain="workspace",
        )
    except Exception as exc:
        failure = str(exc).strip()
        log_agent_action_event(
            conversation_id=conversation_id,
            event_kind="failed",
            action_kind="write_file",
            risk_level="high",
            access_mode=access_mode,
            title="Write file on host",
            summary=f"{'Append to' if append else 'Write'} `{path}` in the Jarvin workspace.",
            path=path,
            content_preview=content,
            client_session_id=client_session_id,
            diff_preview=diff_preview,
            detail=failure,
        )
        return ToolChatResponse(
            handled=True,
            reply=f"I couldn't write that file. {failure}".strip(),
            active_domain="workspace",
        )
