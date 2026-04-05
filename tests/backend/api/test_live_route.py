from __future__ import annotations

import threading
import time

import pytest

import backend.api.routes.live as live_mod
import backend.listener.live_state as live_state


@pytest.fixture(autouse=True)
def _reset_live_state():
    live_state._reset_for_tests()
    yield
    live_state._reset_for_tests()


@pytest.mark.asyncio
async def test_live_latest_includes_revision_metadata():
    live_state.notify_ui_update(event_kind="conversation", conversation_id=17)

    snapshot = await live_mod.live_latest()

    assert snapshot["rev"] == 1
    assert snapshot["event_kind"] == "conversation"
    assert snapshot["event_conversation_id"] == 17


def test_wait_next_wakes_on_ui_update():
    observed: dict[str, object] = {}

    def waiter():
        observed["snapshot"] = live_state.wait_next(0, timeout=1.0)

    thread = threading.Thread(target=waiter)
    thread.start()
    time.sleep(0.05)
    live_state.notify_ui_update(event_kind="agent_action", conversation_id=9)
    thread.join(timeout=1.0)

    assert not thread.is_alive()
    snapshot = observed["snapshot"]
    assert isinstance(snapshot, dict)
    assert snapshot["rev"] == 1
    assert snapshot["event_kind"] == "agent_action"
    assert snapshot["event_conversation_id"] == 9


def test_format_sse_includes_event_id_and_payload():
    payload = {
        "rev": 3,
        "seq": 1,
        "event_kind": "conversation",
        "event_conversation_id": 5,
    }

    formatted = live_mod._format_sse(payload)

    assert "id: 3" in formatted
    assert "event: live" in formatted
    assert '"event_conversation_id": 5' in formatted
