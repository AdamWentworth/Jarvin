from __future__ import annotations


def finalize_tool_response_impl(
    response,
    *,
    conversation_id,
    remember_active_follow_up_domain,
):
    if response.handled and response.active_domain:
        remember_active_follow_up_domain(conversation_id, response.active_domain)
    return response


def safe_tool_call_impl(
    *,
    ToolChatResponse,
    fn,
    fallback: str,
    active_domain: str | None = None,
):
    try:
        return ToolChatResponse(handled=True, reply=fn(), active_domain=active_domain)
    except Exception as exc:
        detail = str(exc).strip()
        if detail:
            return ToolChatResponse(handled=True, reply=f"{fallback} {detail}", active_domain=active_domain)
        return ToolChatResponse(handled=True, reply=fallback, active_domain=active_domain)
