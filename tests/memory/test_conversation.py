# tests/memory/test_conversation.py
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

import config as cfg


def _reload_conversation(tmp_path):
    """
    Point the DB at a temp directory and reload memory.conversation so its
    module-level connection uses the temp DB.
    """
    cfg.settings.data_dir = str(tmp_path)
    cfg.settings.db_filename = "conv_test.sqlite3"

    import memory.conversation as conv
    importlib.reload(conv)
    return conv


def test_bootstrap_creates_default_conversation(tmp_path):
    conv = _reload_conversation(tmp_path)

    items = conv.list_conversations()
    assert len(items) >= 1
    # newest first
    latest = items[0]
    assert "id" in latest and "title" in latest
    assert latest["messages"] == 0

    cid = conv.get_active_conversation_id()
    assert isinstance(cid, int)


def test_multi_conversation_lifecycle(tmp_path):
    conv = _reload_conversation(tmp_path)

    # start with clean default
    base_items = conv.list_conversations()
    base_count = len(base_items)
    base_active = conv.get_active_conversation_id()

    # create new + activate
    new_id = conv.new_conversation("Test convo", activate=True)
    assert isinstance(new_id, int)
    assert conv.get_active_conversation_id() == new_id

    # append a couple of turns
    conv.append_turn("user", "hello", conversation_id=new_id)
    conv.append_turn("assistant", "hi", conversation_id=new_id)
    hist = conv.get_conversation_history(conversation_id=new_id)
    assert hist == [("user", "hello"), ("assistant", "hi")]

    # rename active
    conv.rename_conversation(new_id, "Renamed convo")
    items = conv.list_conversations()
    titles = [it["title"] for it in items]
    assert "Renamed convo" in titles

    # switch back to original active
    conv.set_active_conversation(base_active)
    assert conv.get_active_conversation_id() == base_active

    # delete the new conversation; total count should drop by 1
    conv.delete_conversation(new_id)
    items_after = conv.list_conversations()
    assert len(items_after) == max(1, base_count)  # at least one always exists
    ids_after = [it["id"] for it in items_after]
    assert new_id not in ids_after


def test_clear_conversation_and_history_roundtrip(tmp_path):
    conv = _reload_conversation(tmp_path)
    cid = conv.get_active_conversation_id()

    conv.append_turn("user", "u1", cid)
    conv.append_turn("assistant", "a1", cid)
    assert len(conv.get_conversation_history(cid)) == 2

    conv.clear_conversation(cid)
    assert conv.get_conversation_history(cid) == []


def test_user_profile_upsert_and_get(tmp_path):
    conv = _reload_conversation(tmp_path)  # noqa: F841

    from memory import conversation as conv_mod

    profile_in = {
        "name": "Alice",
        "goal": "Ship Jarvin",
        "mood": "Focused",
        "communication_style": "Direct",
        "response_length": "Concise",
    }
    conv_mod.set_user_profile(profile_in)
    out = conv_mod.get_user_profile()

    assert out["name"] == "Alice"
    assert out["goal"] == "Ship Jarvin"
    assert out["communication_style"] == "Direct"

    # update only some fields
    profile_in2 = {
        "name": "Alice",
        "goal": "Fix tests",
        "mood": "Stressed",
        "communication_style": "Direct",
        "response_length": "Balanced",
    }
    conv_mod.set_user_profile(profile_in2)
    out2 = conv_mod.get_user_profile()
    assert out2["goal"] == "Fix tests"
    assert out2["response_length"] == "Balanced"
