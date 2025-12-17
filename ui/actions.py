# ui/actions.py
from __future__ import annotations
from typing import Tuple, List, Dict

from memory.conversation import (
    # Profile + history (scoped to ACTIVE conversation)
    get_conversation_history, set_conversation_history,
    get_user_profile, set_user_profile, clear_conversation,
    # multi-conversation controls
    list_conversations, new_conversation, rename_conversation, delete_conversation,
    get_active_conversation_id, set_active_conversation,
)

# -------- Profile --------

def save_user_profile(name, goal, mood, communication_style, response_length):
    profile = {
        "name": name,
        "goal": goal,
        "mood": mood,
        "communication_style": communication_style,
        "response_length": response_length,
    }
    set_user_profile(profile)
    return profile


def load_user_profile_fields():
    """
    Returns values (name, goal, mood, communication_style, response_length, status_markdown)
    to populate the Profile tab inputs on app load.
    """
    p = get_user_profile() or {}
    name = p.get("name") or ""
    goal = p.get("goal") or ""
    mood = p.get("mood") or "Focused"
    style = p.get("communication_style") or "Friendly"
    length = p.get("response_length") or "Balanced"

    status = ""
    if any([name, goal]):
        status = f"📦 Loaded saved profile for **{name or 'User'}**."

    return name, goal, mood, style, length, status


# -------- Conversation history (active) --------

def clear_conversation_history():
    clear_conversation()
    return get_conversation_history()


def update_history_display(history):
    """
    Convert the flat [(role, message)] history into Chatbot-style
    [[user_message, assistant_message], ...] pairs.

    - Consecutive user messages get flushed with empty assistant text.
    - Orphan assistant messages get paired with "" as the user side.
    """
    if not history:
        return []

    pairs: List[List[str]] = []
    pending_user: str | None = None

    for role, message in history:
        if not message:
            continue
        text = str(message)

        if role == "user":
            # If there was a previous user without a reply yet, flush it.
            if pending_user is not None:
                pairs.append([pending_user, ""])
            pending_user = text
        else:  # assistant
            if pending_user is None:
                # Assistant with no explicit user just before
                pairs.append(["", text])
            else:
                pairs.append([pending_user, text])
                pending_user = None

    # Trailing user with no assistant reply yet
    if pending_user is not None:
        pairs.append([pending_user, ""])

    return pairs


def get_save_confirmation():
    profile = get_user_profile()
    return f"✅ Profile saved! Jarvin will remember: {profile.get('name','Unknown')} - {profile.get('goal','No goal set')}"


# -------- Multi-conversation helpers for UI --------

def _fmt_choice(item: Dict) -> str:
    """
    Render as just the title, no IDs or message counts.
    Fallback to a generic name if title is empty.
    """
    title = (item.get("title") or "").strip()
    if not title:
        # Backend always sets a title, but keep a safe fallback.
        return "Conversation"
    return title


def get_conversation_menu():
    """
    Returns (choices, selected_value, subtitle_markdown) for the Conversations UI.
    - choices: plain conversation titles (strings)
    - selected_value: the active conversation's title
    - subtitle_markdown: kept for wiring compatibility; currently always "".
    """
    items = list_conversations()
    active = get_active_conversation_id()
    choices = [_fmt_choice(it) for it in items]
    selected = None

    for it in items:
        if it["id"] == active:
            selected = _fmt_choice(it)
            break

    if selected is None and choices:
        selected = choices[0]

    # No “Active: …” text anymore
    subtitle = ""
    return choices, selected, subtitle

def activate_conversation(value: str | None):
    """
    Activate a conversation based on its title (the Radio's value).

    If multiple conversations share the same title, this selects the first
    one returned by list_conversations() (newest first).
    """
    title = (value or "").strip()
    if not title:
        return get_conversation_menu(), get_conversation_history()

    items = list_conversations()
    cid = None
    for it in items:
        if (it.get("title") or "").strip() == title:
            cid = it["id"]
            break

    if cid is None:
        # Fallback: if something went wrong, leave active as-is but refresh menu/history.
        return get_conversation_menu(), get_conversation_history()

    set_active_conversation(int(cid))
    return get_conversation_menu(), get_conversation_history()


def create_conversation(title: str | None):
    """
    Create a new conversation and make it active.
    If title is falsy, the backend will assign a default.
    """
    cid = new_conversation((title or "").strip() or None, activate=True)
    return get_conversation_menu(), get_conversation_history()


def rename_active_conversation(new_title: str | None):
    """
    Rename the active conversation.
    """
    active = get_active_conversation_id()
    rename_conversation(active, (new_title or "").strip() or "Conversation")
    return get_conversation_menu()


def delete_active_conversation():
    """
    Delete the active conversation if there is more than one total.

    Returns:
      (menu_tuple, history, error_message)

      - menu_tuple: (choices, selected, subtitle)
      - history: conversation history for the new active conversation
      - error_message: "" if deletion succeeded, otherwise a reason string
    """
    items = list_conversations()
    if len(items) <= 1:
        # Block deletion if it is the only conversation.
        menu = get_conversation_menu()
        history = get_conversation_history()
        return menu, history, "Cannot delete the only conversation."

    active = get_active_conversation_id()
    delete_conversation(active)
    # After deletion, an active convo is guaranteed; return its menu + history
    return get_conversation_menu(), get_conversation_history(), ""
