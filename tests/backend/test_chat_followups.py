from __future__ import annotations

import backend.agent.chat.assistant_chat_tools as chat_tools
import backend.agent.chat.chat_followup_context as followup_context
import backend.agent.workspace.workspace_request_tools as workspace_tools


def test_workspace_read_follow_up_show_more_is_handled(monkeypatch):
    conversation_id = 17
    calls = []

    monkeypatch.setattr(
        chat_tools,
        "_read_file_reply",
        lambda path, start_line=1, end_line=None: calls.append((path, start_line, end_line)) or f"Read `{path}` from {start_line}",
        raising=True,
    )

    try:
        first = chat_tools.maybe_handle_assistant_tool_request(
            "Pull up backend/api/app.py lines 1 to 20",
            conversation_id=conversation_id,
        )
        second = chat_tools.maybe_handle_assistant_tool_request(
            "show me more",
            conversation_id=conversation_id,
        )

        assert first.handled is True
        assert second.handled is True
        assert calls[0] == ("backend/api/app.py", 1, 20)
        assert calls[1][0] == "backend/api/app.py"
        assert calls[1][1] == 21
    finally:
        workspace_tools.clear_workspace_context(conversation_id)


def test_active_follow_up_prefers_most_recent_brief_over_stale_weather_context(monkeypatch):
    conversation_id = 31
    weather_calls = []

    def fake_weather(text, conversation_id=None):
        weather_calls.append(text)
        if "weather" in text.lower():
            return type(
                "WeatherTool",
                (),
                {
                    "reply": "Today in Seattle: Clear sky.",
                    "payload": {"location_label": "Seattle", "icon_name": "sun"},
                },
            )()
        if text == "How about tomorrow?":
            return type(
                "WeatherTool",
                (),
                {
                    "reply": "Tomorrow in Seattle: Rainy.",
                    "payload": {"location_label": "Seattle", "icon_name": "cloud-rain"},
                },
            )()
        return None

    monkeypatch.setattr(chat_tools, "maybe_handle_weather_request", fake_weather, raising=True)
    monkeypatch.setattr(
        chat_tools,
        "maybe_handle_brief_request",
        lambda text, conversation_id=None: (
            "Morning brief output"
            if text == "give me my morning brief"
            else "Tomorrow brief output"
            if text == "How about tomorrow?"
            else None
        ),
        raising=True,
    )

    try:
        weather = chat_tools.maybe_handle_assistant_tool_request(
            "What's the weather in Seattle?",
            conversation_id=conversation_id,
        )
        brief = chat_tools.maybe_handle_assistant_tool_request(
            "give me my morning brief",
            conversation_id=conversation_id,
        )
        follow_up = chat_tools.maybe_handle_assistant_tool_request(
            "How about tomorrow?",
            conversation_id=conversation_id,
        )

        assert weather.handled is True
        assert brief.handled is True
        assert follow_up.handled is True
        assert follow_up.reply == "Tomorrow brief output"
        assert "How about tomorrow?" not in weather_calls
    finally:
        followup_context.clear_active_follow_up_domain(conversation_id)


def test_active_follow_up_prefers_reminder_time_reply_over_stale_weather_context(monkeypatch):
    conversation_id = 32
    weather_calls = []

    def fake_weather(text, conversation_id=None):
        weather_calls.append(text)
        if "weather" in text.lower():
            return type(
                "WeatherTool",
                (),
                {
                    "reply": "Today in Burnaby: Overcast.",
                    "payload": {"location_label": "Burnaby", "icon_name": "cloud"},
                },
            )()
        if text == "tomorrow at 5pm":
            return type(
                "WeatherTool",
                (),
                {
                    "reply": "Tomorrow in Burnaby: Rain.",
                    "payload": {"location_label": "Burnaby", "icon_name": "cloud-rain"},
                },
            )()
        return None

    monkeypatch.setattr(chat_tools, "maybe_handle_weather_request", fake_weather, raising=True)
    monkeypatch.setattr(
        chat_tools,
        "maybe_handle_reminder_request",
        lambda text, conversation_id=None: (
            "What time should I set reminder `call mom` for?"
            if text == "remind me to call mom"
            else "Saved reminder `call mom` for `2026-04-05 05:00 PM`."
            if text == "tomorrow at 5pm"
            else None
        ),
        raising=True,
    )

    try:
        weather = chat_tools.maybe_handle_assistant_tool_request(
            "What's the weather in Burnaby?",
            conversation_id=conversation_id,
        )
        reminder = chat_tools.maybe_handle_assistant_tool_request(
            "remind me to call mom",
            conversation_id=conversation_id,
        )
        follow_up = chat_tools.maybe_handle_assistant_tool_request(
            "tomorrow at 5pm",
            conversation_id=conversation_id,
        )

        assert weather.handled is True
        assert reminder.handled is True
        assert follow_up.handled is True
        assert follow_up.reply == "Saved reminder `call mom` for `2026-04-05 05:00 PM`."
        assert "tomorrow at 5pm" not in weather_calls
    finally:
        followup_context.clear_active_follow_up_domain(conversation_id)


def test_active_follow_up_prefers_research_over_stale_weather_context(monkeypatch):
    conversation_id = 33
    weather_calls = []

    def fake_weather(text, conversation_id=None):
        weather_calls.append(text)
        if "weather" in text.lower():
            return type(
                "WeatherTool",
                (),
                {
                    "reply": "Today in Seattle: Clear sky.",
                    "payload": {"location_label": "Seattle", "icon_name": "sun"},
                },
            )()
        if text == "What else did you find?":
            return type(
                "WeatherTool",
                (),
                {
                    "reply": "Tomorrow in Seattle: Rainy.",
                    "payload": {"location_label": "Seattle", "icon_name": "cloud-rain"},
                },
            )()
        return None

    seen_queries = []
    monkeypatch.setattr(chat_tools, "maybe_handle_weather_request", fake_weather, raising=True)
    monkeypatch.setattr(
        chat_tools,
        "_web_search_reply",
        lambda query: seen_queries.append(query) or f"Web search from `duckduckgo_lite` for `{query}`:\n- source",
        raising=True,
    )

    try:
        weather = chat_tools.maybe_handle_assistant_tool_request(
            "What's the weather in Seattle?",
            conversation_id=conversation_id,
        )
        research = chat_tools.maybe_handle_assistant_tool_request(
            "Research llama.cpp windows cuda docs for me",
            conversation_id=conversation_id,
        )
        follow_up = chat_tools.maybe_handle_assistant_tool_request(
            "What else did you find?",
            conversation_id=conversation_id,
        )

        assert weather.handled is True
        assert research.handled is True
        assert follow_up.handled is True
        assert "llama.cpp windows cuda docs" in follow_up.reply
        assert seen_queries == ["llama.cpp windows cuda docs", "llama.cpp windows cuda docs"]
        assert "What else did you find?" not in weather_calls
    finally:
        followup_context.clear_active_follow_up_domain(conversation_id)

