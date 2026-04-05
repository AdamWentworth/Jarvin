from __future__ import annotations


def maybe_host_task_response_adapter(
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
    maybe_host_task_response_impl,
):
    return maybe_host_task_response_impl(
        text,
        conversation_id=conversation_id,
        client_session_id=client_session_id,
        agent_access_mode=agent_access_mode,
        ToolChatResponse=ToolChatResponse,
        normalize_agent_access_mode=normalize_agent_access_mode,
        maybe_plan_host_task_request=maybe_plan_host_task_request,
        build_pending_host_task=build_pending_host_task,
        set_pending_host_task=set_pending_host_task,
        get_running_host_task=get_running_host_task,
        build_host_task_payload=build_host_task_payload,
        log_agent_action_event=log_agent_action_event,
    )


def execute_pending_host_task_adapter(
    pending,
    *,
    conversation_id,
    client_session_id,
    ToolChatResponse,
    start_host_task_execution,
    execute_workspace_plan,
    update_latest_tool_turn,
    log_agent_action_event,
):
    return start_host_task_execution(
        pending,
        conversation_id=conversation_id,
        client_session_id=client_session_id,
        ToolChatResponse=ToolChatResponse,
        access_mode="approve_risky",
        execute_workspace_plan=execute_workspace_plan,
        update_latest_tool_turn=update_latest_tool_turn,
        log_agent_action_event=log_agent_action_event,
    )
