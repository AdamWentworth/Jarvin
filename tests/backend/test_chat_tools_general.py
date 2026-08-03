from __future__ import annotations

import backend.agent.chat.chat_tool_helpers as chat_tool_helpers
import backend.agent.chat.assistant_chat_tools as chat_tools
import backend.agent.chat.chat_personal_organization_action_planner as personal_org_planner
from backend.agent.host_action_approvals import clear_host_action_trust, clear_pending_host_approval
from backend.agent.chat.chat_request_planner import PlannedToolRoute, PlannedToolStep
from backend.agent.integration_facade import (
    CalendarAgendaResult,
    CalendarEventDetails,
    CalendarEventMatch,
    CalendarEventSummary,
    WebPageExtract,
    WebResearchResult,
    WebSearchItem,
)


def test_natural_language_weather_request_is_handled(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "maybe_handle_weather_request",
        lambda text, conversation_id=None: type(
            "WeatherTool",
            (),
            {
                "reply": "Today in Seattle, Washington, United States: Clear sky.",
                "payload": {
                    "location_label": "Seattle, Washington, United States",
                    "summary": "Clear sky",
                    "icon_name": "sun",
                },
            },
        )(),
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request("What's the weather in Seattle?")
    assert response.handled is True
    assert "Clear sky" in response.reply
    assert response.tool_kind == "weather"
    assert response.tool_payload["icon_name"] == "sun"


def test_top_level_planner_routes_to_organizer_before_legacy_domain_checks(monkeypatch):
    seen = []
    monkeypatch.setattr(
        chat_tools,
        "maybe_plan_personal_organization_request",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "maybe_plan_tool_request_route",
        lambda text, active_domain=None: PlannedToolRoute(
            is_tool_request=True,
            domain="organizer",
            normalized_request="show all my calendar events and reminders",
            confidence="high",
            reason="Combined overview request.",
        ),
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "maybe_organizer_tool_response_impl",
        lambda text, *, conversation_id, ToolChatResponse: seen.append(text)
        or ToolChatResponse(handled=True, reply="Current overview:\n- reminder\n- event", active_domain="organizer"),
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "maybe_handle_reminder_request",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("reminder handler should not run first")),
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request(
        "Could you give me the whole picture of my schedule and reminders?"
    )

    assert response.handled is True
    assert response.active_domain == "organizer"
    assert "Current overview:" in response.reply
    assert seen == ["Could you give me the whole picture of my schedule and reminders?"]


def test_combined_overview_shortcuts_to_organizer_even_if_planner_is_wrong(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "maybe_plan_tool_request_route",
        lambda text, active_domain=None: PlannedToolRoute(
            is_tool_request=True,
            domain="reminder",
            normalized_request="show all reminders and events",
            confidence="high",
            reason="Wrong planner route.",
        ),
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "execute_organizer_action",
        lambda action, *, text, conversation_id: "Current overview:\n- reminder\n- event",
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "maybe_handle_reminder_request",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("reminder handler should not win this route")),
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request(
        "Can you please output all of my reminders and all of my events?"
    )

    assert response.handled is True
    assert response.active_domain == "organizer"
    assert "Current overview:" in response.reply


def test_personal_organization_planner_executes_structured_reminder_action_without_reparsing(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "maybe_plan_personal_organization_request",
        lambda *args, **kwargs: personal_org_planner.PersonalOrganizationPlan(
            confidence="high",
            actions=(
                personal_org_planner.PersonalOrganizationAction(
                    domain="reminder",
                    action="move",
                    query="Go to Costco",
                    when_text="tomorrow at 9am",
                ),
            ),
            reason="Structured reminder move.",
        ),
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "maybe_handle_reminder_request",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("free-text reminder parser should not run")),
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "execute_reminder_plan",
        lambda plan, conversation_id=None: f"Moved `{plan.query}` to `{plan.when_text}`.",
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request(
        "Please change that reminder to tomorrow at 9am."
    )

    assert response.handled is True
    assert response.active_domain == "reminder"
    assert "Moved `Go to Costco`" in response.reply


def test_personal_organization_planner_acknowledges_single_reminder_target_confirmation(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "get_active_follow_up_domain",
        lambda conversation_id: "reminder",
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "get_reminder_context",
        lambda conversation_id: type(
            "ReminderContext",
            (),
            {"last_action": "move", "last_title": "Go to Costco", "last_listed_ids": (1,)},
        )(),
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "maybe_handle_reminder_request",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("free-text reminder parser should not run")),
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request(
        "the one and only that we have please.",
        conversation_id=991,
    )

    assert response.handled is True
    assert response.active_domain == "reminder"
    assert "I'm looking at reminder `Go to Costco`." in response.reply


def test_personal_organization_planner_keeps_time_update_actionable(monkeypatch):
    reminder_context = type(
        "ReminderContext",
        (),
        {"last_action": "move", "last_title": "Go to Costco", "last_listed_ids": (1,)},
    )()
    monkeypatch.setattr(
        personal_org_planner,
        "generate_reply",
        lambda *args, **kwargs: (
            '{"is_personal_organization_request": true, "confidence": "high", "reason": "Reminder update.", '
            '"actions": [{"domain": "reminder", "action": "move", "query": "Go to Costco", "when_text": "9 a.m", '
            '"normalized_request": "move reminder Go to Costco to 9 a.m"}]}'
        ),
        raising=True,
    )

    plan = personal_org_planner.maybe_plan_personal_organization_request(
        "Yes, that is the one. Please make sure that is at 9 a.m.",
        active_domain="reminder",
        reminder_context=reminder_context,
        calendar_context=None,
        organizer_context=None,
    )

    assert plan is not None
    assert plan.actions[0].action == "move"
    assert plan.actions[0].query == "Go to Costco"


def test_top_level_planner_executes_compound_steps(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "maybe_plan_personal_organization_request",
        lambda *args, **kwargs: None,
        raising=True,
    )
    seen_reminder_prompts = []
    monkeypatch.setattr(
        chat_tools,
        "maybe_plan_tool_request_route",
        lambda text, active_domain=None: PlannedToolRoute(
            is_tool_request=True,
            domain="compound",
            normalized_request=None,
            confidence="high",
            reason="Two separate actions.",
            steps=(
                PlannedToolStep(domain="reminder", prompt="delete the reminder called Old reminder"),
                PlannedToolStep(domain="calendar", prompt="move the lunch event to tomorrow at 2pm"),
            ),
        ),
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "maybe_handle_reminder_request",
        lambda text, conversation_id=None: seen_reminder_prompts.append(text) or (
            "Deleted reminder `Old reminder`." if "Old reminder" in text else None
        ),
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "_maybe_calendar_tool_response",
        lambda text, conversation_id=None: chat_tools.ToolChatResponse(
            handled=True,
            reply="I found `Lunch` scheduled for `tomorrow at noon`. Reply `yes` to move it to `tomorrow at 2pm`, or `cancel` to leave it alone.",
            active_domain="calendar",
        )
        if text == "move the lunch event to tomorrow at 2pm"
        else None,
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request(
        "Please delete the reminder called Old reminder and move the lunch event to tomorrow at 2pm."
    )

    assert response.handled is True
    assert "Reply `yes` to move it" in response.reply
    assert any("Old reminder" in prompt for prompt in seen_reminder_prompts)


def test_meta_clarification_question_falls_back_instead_of_hitting_reminder_tools(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "maybe_plan_personal_organization_request",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "maybe_plan_tool_request_route",
        lambda text, active_domain=None: None,
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "maybe_handle_reminder_request",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("reminder handler should not run")),
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request(
        "Okay now to be clear is that a reminder or is that an event?",
        conversation_id=81,
    )

    assert response.handled is False


def test_meta_clarification_reports_recent_calendar_and_reminder(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "maybe_plan_personal_organization_request",
        lambda *args, **kwargs: None,
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "maybe_plan_tool_request_route",
        lambda text, active_domain=None: None,
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "get_calendar_context",
        lambda conversation_id: type(
            "CalendarContext",
            (),
            {"last_action": "create", "last_query": "go to Costco tomorrow at 12 noon"},
        )(),
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "get_reminder_context",
        lambda conversation_id: type(
            "ReminderContext",
            (),
            {"last_action": "create", "last_title": "Go to Costco"},
        )(),
        raising=True,
    )
    monkeypatch.setattr(
        chat_tools,
        "maybe_handle_reminder_request",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("reminder handler should not run")),
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request(
        "Okay now to be clear is that a reminder or is that an event?",
        conversation_id=81,
    )

    assert response.handled is True
    assert response.active_domain == "organizer"
    assert "That created both" in response.reply


def test_natural_language_calendar_setup_phrase_reports_local_calendar_ready():
    response = chat_tools.maybe_handle_assistant_tool_request("connect my calendar")
    assert response.handled is True
    assert "built-in calendar is ready" in response.reply


def test_natural_language_google_calendar_phrase_uses_calendar_not_search(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "maybe_plan_calendar_request",
        lambda text, conversation_id=None: chat_tools.CalendarPlan(
            is_calendar_request=True,
            action="lookup",
            window_days=7,
        ),
        raising=True,
    )
    monkeypatch.setattr(
        chat_tool_helpers,
        "get_calendar_agenda",
        lambda window_days=7: CalendarAgendaResult(
            calendar_id="primary",
            window_days=window_days,
            events=[
                CalendarEventSummary(
                    starts_at="2026-04-04 09:00 AM",
                    title="Morning standup",
                    location="Home office",
                )
            ],
        ),
        raising=True,
    )
    monkeypatch.setattr(
        chat_tool_helpers,
        "browse_search_results",
        lambda query: (_ for _ in ()).throw(AssertionError("web search should not run for Google Calendar lookup")),
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request(
        "Please just look at my Google Calendar and tell me what I have this week."
    )

    assert response.handled is True
    assert "Morning standup" in response.reply


def test_natural_language_calendar_follow_up_week_lookup_is_handled(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "maybe_plan_calendar_request",
        lambda text, conversation_id=None: chat_tools.CalendarPlan(
            is_calendar_request=True,
            action="lookup",
            window_days=7,
        ),
        raising=True,
    )
    monkeypatch.setattr(
        chat_tool_helpers,
        "get_calendar_agenda",
        lambda window_days=7: CalendarAgendaResult(
            calendar_id="primary",
            window_days=window_days,
            events=[
                CalendarEventSummary(
                    starts_at="2026-04-05 01:00 PM",
                    title="Project sync",
                    location="Zoom",
                )
            ],
        ),
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request(
        "How about instead if you just look at all the events for the upcoming week and give me anything that's actually real"
    )

    assert response.handled is True
    assert "Project sync" in response.reply


def test_natural_language_google_request_falls_back_when_google_is_not_configured(monkeypatch):
    monkeypatch.setattr(chat_tools.cfg.settings, "agent_web_search_provider", "duckduckgo_lite", raising=False)
    monkeypatch.setattr(chat_tool_helpers, "google_search_is_configured", lambda: False, raising=True)
    monkeypatch.setattr(
        chat_tool_helpers,
        "browse_search_results",
        lambda query: WebResearchResult(
            provider="duckduckgo_lite",
            query=query,
            items=[WebSearchItem(title="Jarvin docs", url="https://example.com", snippet="Search result")],
            pages=[
                WebPageExtract(
                    url="https://example.com",
                    title="Jarvin docs",
                    excerpt="Jarvin supports local tools and mobile voice access.",
                )
            ],
        ),
        raising=True,
    )
    monkeypatch.setattr(chat_tool_helpers, "generate_reply", lambda *args, **kwargs: "- Jarvin supports local tools [1].", raising=True)

    response = chat_tools.maybe_handle_assistant_tool_request("Google Jarvin docs")
    assert response.handled is True
    assert "not configured on this host" in response.reply
    assert "https://example.com" in response.reply
    assert "local tools [1]" in response.reply


def test_natural_language_research_request_is_handled(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "_web_search_reply",
        lambda query: f"Web search from `duckduckgo_lite` for `{query}`:\n- source",
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request(
        "Could you look into local llm benchmark results and summarize what you find?"
    )

    assert response.handled is True
    assert "local llm benchmark results" in response.reply


def test_research_follow_up_reuses_prior_query(monkeypatch):
    conversation_id = 18
    seen = []
    monkeypatch.setattr(
        chat_tools,
        "_web_search_reply",
        lambda query: seen.append(query) or f"Web search from `duckduckgo_lite` for `{query}`:\n- source",
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request(
        "Research llama.cpp windows cuda docs for me",
        conversation_id=conversation_id,
    )
    follow_up = chat_tools.maybe_handle_assistant_tool_request(
        "What else did you find?",
        conversation_id=conversation_id,
    )

    assert response.handled is True
    assert follow_up.handled is True
    assert seen == ["llama.cpp windows cuda docs", "llama.cpp windows cuda docs"]


def test_natural_language_repo_search_is_handled(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "_repo_search_reply",
        lambda query: f"Search results for `{query}`:\n- `backend/api/app.py:1` include_router(...)",
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request("search the repo for include_router")
    assert response.handled is True
    assert "include_router" in response.reply


def test_fuzzy_workspace_repo_search_is_handled(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "_repo_search_reply",
        lambda query: f"Search results for `{query}`:\n- `backend/api/app.py:1` include_router(...)",
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request("Could you look through the codebase for include_router?")

    assert response.handled is True
    assert "include_router" in response.reply


def test_natural_language_run_requires_approval_by_default(monkeypatch):
    conversation_id = 41
    monkeypatch.setattr(chat_tools, "_run_reply", lambda command: (_ for _ in ()).throw(AssertionError("should not execute")), raising=True)

    try:
        response = chat_tools.maybe_handle_assistant_tool_request("run git status", conversation_id=conversation_id)
    finally:
        clear_pending_host_approval(conversation_id)

    assert response.handled is True
    assert response.tool_kind == "approval_request"
    assert response.tool_payload["status"] == "pending"
    assert response.tool_payload["action_kind"] == "run_command"
    assert response.tool_payload["can_approve"] is True


def test_natural_language_run_executes_with_full_access(monkeypatch):
    monkeypatch.setattr(chat_tools, "_run_reply", lambda command: f"Command `{command}` exited with `0`.", raising=True)

    response = chat_tools.maybe_handle_assistant_tool_request("run git status", agent_access_mode="full_access")
    assert response.handled is True
    assert "git status" in response.reply


def test_fuzzy_workspace_git_question_is_handled(monkeypatch):
    monkeypatch.setattr(chat_tools, "_run_reply", lambda command: f"Command `{command}` exited with `0`.", raising=True)

    response = chat_tools.maybe_handle_assistant_tool_request(
        "What changed recently in the repo?",
        conversation_id=512,
        agent_access_mode="full_access",
    )

    assert response.handled is True
    assert "git diff --stat" in response.reply


def test_tool_write_is_blocked_in_read_only_mode():
    response = chat_tools.maybe_handle_tool_command(
        "/tool write notes/test.txt\nhello from jarvin",
        agent_access_mode="read_only",
    )

    assert response.handled is True
    assert response.tool_kind == "approval_request"
    assert response.tool_payload["status"] == "blocked"
    assert response.tool_payload["action_kind"] == "write_file"
    assert response.tool_payload["can_approve"] is False


def test_pending_host_command_can_be_approved(monkeypatch):
    conversation_id = 42
    monkeypatch.setattr(chat_tools, "_run_reply", lambda command: f"Command `{command}` exited with `0`.", raising=True)
    monkeypatch.setattr(chat_tools, "update_latest_tool_turn", lambda **kwargs: True, raising=True)

    try:
        pending = chat_tools.maybe_handle_assistant_tool_request(
            "run git status",
            conversation_id=conversation_id,
            agent_access_mode="approve_risky",
        )
        approved = chat_tools.maybe_handle_assistant_tool_request("approve", conversation_id=conversation_id)
    finally:
        clear_pending_host_approval(conversation_id)

    assert pending.handled is True
    assert pending.tool_kind == "approval_request"
    assert approved.handled is True
    assert "git status" in approved.reply


def test_pending_host_command_can_be_denied(monkeypatch):
    conversation_id = 43
    monkeypatch.setattr(chat_tools, "_run_reply", lambda command: (_ for _ in ()).throw(AssertionError("should not execute")), raising=True)
    monkeypatch.setattr(chat_tools, "update_latest_tool_turn", lambda **kwargs: True, raising=True)

    try:
        pending = chat_tools.maybe_handle_assistant_tool_request(
            "run git status",
            conversation_id=conversation_id,
            agent_access_mode="approve_risky",
        )
        denied = chat_tools.maybe_handle_assistant_tool_request("deny", conversation_id=conversation_id)
    finally:
        clear_pending_host_approval(conversation_id)

    assert pending.handled is True
    assert pending.tool_kind == "approval_request"
    assert denied.handled is True
    assert "canceled that pending host action" in denied.reply.lower()


def test_pending_host_command_can_trust_conversation(monkeypatch):
    conversation_id = 44
    seen_commands: list[str] = []
    monkeypatch.setattr(
        chat_tools,
        "_run_reply",
        lambda command: seen_commands.append(command) or f"Command `{command}` exited with `0`.",
        raising=True,
    )
    monkeypatch.setattr(chat_tools, "update_latest_tool_turn", lambda **kwargs: True, raising=True)

    try:
        pending = chat_tools.maybe_handle_assistant_tool_request(
            "run git status",
            conversation_id=conversation_id,
            agent_access_mode="approve_risky",
        )
        trusted = chat_tools.maybe_handle_assistant_tool_request("trust this chat", conversation_id=conversation_id)
        follow_up = chat_tools.maybe_handle_assistant_tool_request(
            "run git diff --stat",
            conversation_id=conversation_id,
            agent_access_mode="approve_risky",
        )
    finally:
        clear_pending_host_approval(conversation_id)
        clear_host_action_trust(conversation_id)

    assert pending.handled is True
    assert pending.tool_kind == "approval_request"
    assert trusted.handled is True
    assert "git status" in trusted.reply
    assert follow_up.handled is True
    assert follow_up.tool_kind is None
    assert "git diff --stat" in follow_up.reply
    assert seen_commands == ["git status", "git diff --stat"]


def test_pending_host_command_can_trust_session_across_conversations(monkeypatch):
    session_id = "session-abc"
    seen_commands: list[str] = []
    monkeypatch.setattr(
        chat_tools,
        "_run_reply",
        lambda command: seen_commands.append(command) or f"Command `{command}` exited with `0`.",
        raising=True,
    )
    monkeypatch.setattr(chat_tools, "update_latest_tool_turn", lambda **kwargs: True, raising=True)

    try:
        pending = chat_tools.maybe_handle_assistant_tool_request(
            "run git status",
            conversation_id=45,
            client_session_id=session_id,
            agent_access_mode="approve_risky",
        )
        trusted = chat_tools.maybe_handle_assistant_tool_request(
            "trust this session",
            conversation_id=45,
            client_session_id=session_id,
        )
        follow_up = chat_tools.maybe_handle_assistant_tool_request(
            "run git diff --stat",
            conversation_id=46,
            client_session_id=session_id,
            agent_access_mode="approve_risky",
        )
    finally:
        clear_pending_host_approval(45)
        clear_pending_host_approval(46)
        clear_host_action_trust(45, session_id, scope="session")

    assert pending.handled is True
    assert pending.tool_kind == "approval_request"
    assert pending.tool_payload["can_trust_session"] is True
    assert trusted.handled is True
    assert "git status" in trusted.reply
    assert follow_up.handled is True
    assert follow_up.tool_kind is None
    assert "git diff --stat" in follow_up.reply
    assert seen_commands == ["git status", "git diff --stat"]


def test_natural_language_reminder_request_is_handled(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "maybe_handle_reminder_request",
        lambda text, conversation_id=None: "Saved reminder `call mom` for `2026-04-05 05:00 PM`.",
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request("remind me to call mom tomorrow at 5pm")

    assert response.handled is True
    assert "Saved reminder" in response.reply


def test_natural_language_brief_request_is_handled(monkeypatch):
    monkeypatch.setattr(
        chat_tools,
        "maybe_handle_brief_request",
        lambda text, conversation_id=None: "Morning brief output",
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request("give me my morning brief")

    assert response.handled is True
    assert response.reply == "Morning brief output"


def test_natural_language_calendar_create_is_handled(monkeypatch):
    monkeypatch.setattr(
        chat_tool_helpers,
        "create_calendar_event_from_text",
        lambda details: CalendarEventSummary(
            starts_at="2026-04-04 12:00 PM",
            title="Lunch with Sam",
            location="Cafe Vita",
        ),
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request(
        "Schedule lunch with Sam tomorrow at noon on my calendar"
    )

    assert response.handled is True
    assert "Created `Lunch with Sam`" in response.reply
    assert "Cafe Vita" in response.reply


def test_natural_language_calendar_details_are_returned(monkeypatch):
    monkeypatch.setattr(
        chat_tool_helpers,
        "find_calendar_events",
        lambda query: [
            CalendarEventMatch(
                event_id="evt-0",
                title="Lunch with Sam",
                starts_at="2026-04-05T12:00:00-07:00",
                ends_at="2026-04-05T13:00:00-07:00",
                location="Cafe Vita",
                description="Bring the project notes.",
            )
        ],
        raising=True,
    )
    monkeypatch.setattr(
        chat_tool_helpers,
        "get_calendar_event_details",
        lambda event_id, calendar_id=None: CalendarEventDetails(
            event_id=event_id,
            calendar_id=calendar_id or "primary",
            starts_at="2026-04-05 12:00 PM",
            ends_at="2026-04-05 01:00 PM",
            title="Lunch with Sam",
            location="Cafe Vita",
            description="Bring the project notes.",
        ),
        raising=True,
    )

    response = chat_tools.maybe_handle_assistant_tool_request("Show event details for lunch with Sam on my calendar")

    assert response.handled is True
    assert "Details for `Lunch with Sam`" in response.reply
    assert "Bring the project notes." in response.reply

