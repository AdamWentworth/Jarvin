from __future__ import annotations

import pytest

from backend.agent.chat import assistant_chat_tools as chat_tools
from backend.agent.chat.chat_capability_guard import maybe_guard_unhandled_managed_request


@pytest.mark.parametrize(
    ("message", "domain", "operation"),
    [
        ("Please delete all my calendar events.", "calendar", "delete"),
        ("Change the one reminder we have to 9 AM.", "reminder", "update"),
        ("Show all my calendar events and reminders.", "organizer", "read"),
        ("Will it rain in Burnaby tomorrow?", "weather", "read"),
        ("I didn't say Google search, I said Google Calendar.", "calendar", "unknown"),
    ],
)
def test_guard_classifies_unhandled_managed_requests(message, domain, operation):
    decision = maybe_guard_unhandled_managed_request(message)

    assert decision is not None
    assert decision.domain == domain
    assert decision.operation == operation
    assert decision.payload()["status"] == "not_executed"
    assert "did not" in decision.reply.lower()


@pytest.mark.parametrize(
    "message",
    [
        "Why do people use calendar software?",
        "Explain how weather systems form.",
        "Tell me a joke about appointments.",
        "Thanks, that helps.",
    ],
)
def test_guard_does_not_capture_general_conversation(message):
    assert maybe_guard_unhandled_managed_request(message) is None


def test_guard_uses_active_domain_for_ambiguous_action_follow_up():
    decision = maybe_guard_unhandled_managed_request(
        "Change that one to 9 AM.",
        active_domain="reminder",
    )

    assert decision is not None
    assert decision.domain == "reminder"
    assert decision.operation == "update"


def test_assistant_router_returns_structured_guard_instead_of_llm_fallback(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "maybe_handle_natural_language_tool_request",
        lambda *args, **kwargs: chat_tools.ToolChatResponse(handled=False),
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request(
        "You don't need to create anything. Change the existing reminder to 9 AM.",
        conversation_id=991,
    )

    assert response.handled is True
    assert response.tool_kind == "capability_guard"
    assert response.tool_payload == {
        "status": "not_executed",
        "domain": "reminder",
        "operation": "update",
        "explanation": "No deterministic tool accepted this request, so Jarvin blocked free-form model fallback.",
        "examples": [
            "Show my pending reminders.",
            "Remind me tomorrow at 9 AM to go to Costco.",
        ],
    }
