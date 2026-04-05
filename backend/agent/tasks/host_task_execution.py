from __future__ import annotations

import threading

import backend.agent.host_tool_runtime as host_tool_runtime
from backend.agent.tasks.host_task_state import (
    HostTaskStepPlan,
    PendingHostTask,
    build_host_task_payload,
    build_host_task_step_result,
    clear_running_host_task,
    set_running_host_task,
)
from backend.agent.workspace.workspace_request_tools import WorkspacePlan
from backend.ai_engine import build_jarvin_config, generate_reply


def start_host_task_execution(
    pending: PendingHostTask,
    *,
    conversation_id,
    client_session_id,
    ToolChatResponse,
    access_mode: str,
    execute_workspace_plan,
    update_latest_tool_turn,
    log_agent_action_event,
) -> ToolChatResponse:
    running_steps = [build_host_task_step_result(step, status="pending") for step in pending.steps]
    update_latest_tool_turn(
        conversation_id=conversation_id,
        tool_kind="task_request",
        tool_payload=build_host_task_payload(
            pending,
            access_mode=access_mode,
            status="running",
            can_approve=False,
            steps=running_steps,
        ),
        message=f"Running task: {pending.title}",
    )
    set_running_host_task(conversation_id, pending)
    log_agent_action_event(
        conversation_id=conversation_id,
        event_kind="approved",
        action_kind="host_task",
        risk_level=pending.risk_level,
        access_mode=access_mode,
        title=pending.title,
        summary=pending.summary,
        detail="User approved a host task for execution.",
        client_session_id=client_session_id,
    )

    thread = threading.Thread(
        target=_run_host_task,
        name=f"jarvin-host-task-{conversation_id or 'default'}",
        kwargs={
            "pending": pending,
            "conversation_id": conversation_id,
            "client_session_id": client_session_id,
            "access_mode": access_mode,
            "execute_workspace_plan": execute_workspace_plan,
            "update_latest_tool_turn": update_latest_tool_turn,
            "log_agent_action_event": log_agent_action_event,
        },
        daemon=True,
    )
    thread.start()

    return ToolChatResponse(
        handled=True,
        reply=f"Started `{pending.title}`. I'll update the task card as each step finishes.",
        tool_kind="task_request",
        tool_payload=build_host_task_payload(
            pending,
            access_mode=access_mode,
            status="running",
            can_approve=False,
            steps=running_steps,
        ),
        active_domain="workspace",
        persist_assistant_turn=False,
    )


def build_pending_host_task(task, *, conversation_id) -> PendingHostTask:
    steps = tuple(
        HostTaskStepPlan(
            step_id=f"step-{index}",
            title=_step_title(step, index),
            action_kind=str(step.action or "unknown").strip().lower(),
            query=step.query,
            path=step.path,
            start_line=step.start_line,
            end_line=step.end_line,
            command=step.command,
            content=step.content,
            append=bool(step.append),
            preview_block=_initial_step_preview(step),
            risk_level=_step_risk_level(step),
        )
        for index, step in enumerate(task.steps, start=1)
    )
    overall_risk = _overall_risk_level(steps)
    return PendingHostTask(
        title=str(task.title or "Host workspace task").strip() or "Host workspace task",
        summary=str(task.summary or "").strip() or "Execute a multi-step workspace task on the Jarvin host.",
        risk_level=overall_risk,
        steps=steps,
    )


def _run_host_task(
    *,
    pending: PendingHostTask,
    conversation_id,
    client_session_id,
    access_mode: str,
    execute_workspace_plan,
    update_latest_tool_turn,
    log_agent_action_event,
) -> None:
    step_payloads = [build_host_task_step_result(step, status="pending") for step in pending.steps]
    step_summaries: list[str] = []

    try:
        try:
            for index, step in enumerate(pending.steps):
                step_payloads[index] = build_host_task_step_result(
                    step,
                    status="running",
                    preview_block=_resolve_step_preview(step, step_summaries),
                )
                _update_task_turn(
                    pending,
                    conversation_id=conversation_id,
                    access_mode=access_mode,
                    update_latest_tool_turn=update_latest_tool_turn,
                    status="running",
                    step_payloads=step_payloads,
                    message=f"Running task: {pending.title}",
                )

                try:
                    detail, preview_block = _execute_task_step(
                        step,
                        conversation_id=conversation_id,
                        client_session_id=client_session_id,
                        execute_workspace_plan=execute_workspace_plan,
                        step_summaries=step_summaries,
                    )
                except Exception as exc:
                    failure = str(exc).strip() or "Task step failed."
                    step_payloads[index] = build_host_task_step_result(step, status="failed", detail=failure)
                    for remaining_index in range(index + 1, len(step_payloads)):
                        remaining_step = pending.steps[remaining_index]
                        step_payloads[remaining_index] = build_host_task_step_result(
                            remaining_step,
                            status="blocked",
                            detail="Skipped because an earlier step failed.",
                        )
                    _update_task_turn(
                        pending,
                        conversation_id=conversation_id,
                        access_mode=access_mode,
                        update_latest_tool_turn=update_latest_tool_turn,
                        status="failed",
                        step_payloads=step_payloads,
                        message=f"Task failed: {pending.title}",
                    )
                    log_agent_action_event(
                        conversation_id=conversation_id,
                        event_kind="failed",
                        action_kind="host_task",
                        risk_level=pending.risk_level,
                        access_mode=access_mode,
                        title=pending.title,
                        summary=pending.summary,
                        detail=f"{step.title}: {failure}",
                        client_session_id=client_session_id,
                    )
                    return

                step_payloads[index] = build_host_task_step_result(
                    step,
                    status="completed",
                    detail=detail,
                    preview_block=preview_block,
                )
                step_summaries.append(f"{step.title}: {detail}")
                _update_task_turn(
                    pending,
                    conversation_id=conversation_id,
                    access_mode=access_mode,
                    update_latest_tool_turn=update_latest_tool_turn,
                    status="running",
                    step_payloads=step_payloads,
                    message=f"Running task: {pending.title}",
                )

            _update_task_turn(
                pending,
                conversation_id=conversation_id,
                access_mode=access_mode,
                update_latest_tool_turn=update_latest_tool_turn,
                status="completed",
                step_payloads=step_payloads,
                message=f"Completed task: {pending.title}",
            )
            log_agent_action_event(
                conversation_id=conversation_id,
                event_kind="executed",
                action_kind="host_task",
                risk_level=pending.risk_level,
                access_mode=access_mode,
                title=pending.title,
                summary=pending.summary,
                detail="Host task completed successfully.",
                client_session_id=client_session_id,
            )
        except Exception as exc:
            failure = str(exc).strip() or "The host task crashed unexpectedly."
            _update_task_turn(
                pending,
                conversation_id=conversation_id,
                access_mode=access_mode,
                update_latest_tool_turn=update_latest_tool_turn,
                status="failed",
                step_payloads=step_payloads,
                message=f"Task failed: {pending.title}",
            )
            log_agent_action_event(
                conversation_id=conversation_id,
                event_kind="failed",
                action_kind="host_task",
                risk_level=pending.risk_level,
                access_mode=access_mode,
                title=pending.title,
                summary=pending.summary,
                detail=failure,
                client_session_id=client_session_id,
            )
    finally:
        clear_running_host_task(conversation_id)


def _execute_task_step(
    step: HostTaskStepPlan,
    *,
    conversation_id,
    client_session_id,
    execute_workspace_plan,
    step_summaries: list[str],
) -> tuple[str, str | None]:
    if step.action_kind == "write_file":
        return _execute_write_step(step, step_summaries=step_summaries)

    response = execute_workspace_plan(
        _workspace_plan_from_step(step),
        conversation_id=conversation_id,
        client_session_id=client_session_id,
        agent_access_mode="full_access",
    )
    detail = _truncate_detail(response.reply)
    return detail, step.preview_block


def _execute_write_step(step: HostTaskStepPlan, *, step_summaries: list[str]) -> tuple[str, str | None]:
    path = str(step.path or "").strip()
    content = _resolve_step_content(step, step_summaries)
    if not path:
        raise ValueError("Write step is missing a target path.")
    if not content:
        raise ValueError("Write step is missing file content.")

    preview_block = host_tool_runtime.build_write_diff_preview(path, content, append=step.append)
    result = host_tool_runtime.write_file(path, content, append=step.append)
    action = "Appended to" if result.append else "Wrote"
    return f"{action} `{result.path}` ({result.bytes_written} bytes).", preview_block


def _resolve_step_content(step: HostTaskStepPlan, step_summaries: list[str]) -> str:
    content = str(step.content or "")
    summary_block = _task_summary_block(step_summaries)
    if "{{previous_results}}" in content:
        content = content.replace("{{previous_results}}", summary_block)
    if "{{task_summary}}" in content:
        content = content.replace("{{task_summary}}", summary_block)
    return content.strip()


def _resolve_step_preview(step: HostTaskStepPlan, step_summaries: list[str]) -> str | None:
    if step.action_kind != "write_file":
        return step.preview_block
    path = str(step.path or "").strip()
    if not path:
        return step.preview_block
    content = _resolve_step_content(step, step_summaries)
    if not content:
        return step.preview_block
    return host_tool_runtime.build_write_diff_preview(path, content, append=step.append) or step.preview_block


def _task_summary_block(step_summaries: list[str]) -> str:
    if not step_summaries:
        return "No earlier step results were available."
    return "\n".join(f"- {item}" for item in step_summaries if item).strip()


def _update_task_turn(
    pending: PendingHostTask,
    *,
    conversation_id,
    access_mode: str,
    update_latest_tool_turn,
    status: str,
    step_payloads: list[dict[str, object]],
    message: str,
) -> None:
    update_latest_tool_turn(
        conversation_id=conversation_id,
        tool_kind="task_request",
        tool_payload=build_host_task_payload(
            pending,
            access_mode=access_mode,
            status=status,
            can_approve=False,
            steps=step_payloads,
        ),
        message=message,
    )


def _workspace_plan_from_step(step: HostTaskStepPlan) -> WorkspacePlan:
    return WorkspacePlan(
        is_workspace_request=True,
        action=step.action_kind,
        query=step.query,
        path=step.path,
        start_line=step.start_line,
        end_line=step.end_line,
        command=step.command,
        content=step.content,
        append=step.append,
    )


def _step_title(step, index: int) -> str:
    action = str(step.action or "").strip().lower()
    if action == "search_repo":
        return f"Search repo for {step.query or 'query'}"
    if action == "read_file":
        return f"Read {step.path or 'file'}"
    if action == "list_directory":
        return f"List {step.path or '.'}"
    if action == "run_command":
        return f"Run {step.command or 'command'}"
    if action == "write_file":
        verb = "Append to" if getattr(step, "append", False) else "Write"
        return f"{verb} {step.path or 'file'}"
    return f"Step {index}"


def _step_risk_level(step) -> str:
    action = str(step.action or "").strip().lower()
    if action == "run_command":
        return "medium"
    if action == "write_file":
        return "high"
    return "low"


def _overall_risk_level(steps: tuple[HostTaskStepPlan, ...]) -> str:
    if any(step.risk_level == "high" for step in steps):
        return "high"
    if any(step.risk_level == "medium" for step in steps):
        return "medium"
    return "low"


def _initial_step_preview(step) -> str | None:
    action = str(step.action or "").strip().lower()
    if action != "write_file":
        return None

    path = str(step.path or "").strip()
    content = str(step.content or "").strip()
    if not path:
        return None
    if "{{previous_results}}" in content or "{{task_summary}}" in content:
        verb = "append to" if bool(getattr(step, "append", False)) else "write"
        return f"This step will {verb} `{path}` using a generated summary from earlier task results."
    return host_tool_runtime.build_write_diff_preview(path, content, append=bool(getattr(step, "append", False)))


def _truncate_detail(text: str, *, max_chars: int = 260) -> str:
    cleaned = str(text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def _summarize_task_results(pending: PendingHostTask, step_summaries: list[str]) -> str:
    context = "\n".join(f"- {item}" for item in step_summaries if item)
    if not context:
        return f"Completed `{pending.title}`."
    try:
        cfg_obj = build_jarvin_config(
            mode="agent_strong",
            system_instructions=(
                "You summarize completed Jarvin host tasks. "
                "Write 2-4 concise bullet points describing what was checked and what was found. "
                "Do not invent results beyond the provided step outputs."
            ),
            temperature=0.2,
            max_tokens=220,
        )
        reply = generate_reply(
            f"Task title: {pending.title}\nTask summary: {pending.summary}",
            cfg=cfg_obj,
            context=context,
        ).strip()
        if reply:
            return f"Completed `{pending.title}`.\n\n{reply}"
    except Exception:
        pass
    return f"Completed `{pending.title}`:\n" + context
