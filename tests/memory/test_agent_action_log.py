from __future__ import annotations

import config as cfg
import memory.agent_action_log as action_log


def _use_temp_db(tmp_path) -> None:
    cfg.settings.data_dir = str(tmp_path)
    cfg.settings.db_filename = "agent-action-log-test.sqlite3"
    action_log._reset_for_tests()


def test_log_and_list_agent_action_events(tmp_path):
    _use_temp_db(tmp_path)
    try:
        created = action_log.log_agent_action_event(
            conversation_id=7,
            event_kind="requested",
            action_kind="run_command",
            risk_level="medium",
            access_mode="approve_risky",
            title="Run host command",
            summary="Run `git status` on the Jarvin host.",
            command="git status",
            detail="Waiting for approval.",
        )

        items = action_log.list_agent_action_events(limit=10, conversation_id=7)

        assert created["conversation_id"] == 7
        assert created["command"] == "git status"
        assert len(items) == 1
        assert items[0]["id"] == created["id"]
        assert items[0]["event_kind"] == "requested"
        assert items[0]["action_kind"] == "run_command"
    finally:
        action_log._reset_for_tests()


def test_log_truncates_large_content_preview(tmp_path):
    _use_temp_db(tmp_path)
    try:
        created = action_log.log_agent_action_event(
            conversation_id=9,
            event_kind="requested",
            action_kind="write_file",
            risk_level="high",
            access_mode="approve_risky",
            title="Write file on host",
            summary="Write `notes/test.txt` in the Jarvin workspace.",
            path="notes/test.txt",
            content_preview="x" * 500,
        )

        assert created["content_preview"] is not None
        assert len(created["content_preview"]) <= 240
        assert created["content_preview"].endswith("...")
    finally:
        action_log._reset_for_tests()


def test_log_persists_session_scope_argv_and_diff_preview(tmp_path):
    _use_temp_db(tmp_path)
    try:
        created = action_log.log_agent_action_event(
            conversation_id=11,
            event_kind="trusted",
            action_kind="run_command",
            risk_level="medium",
            access_mode="approve_risky",
            title="Run host command",
            summary="Run `git diff --stat` on the Jarvin host.",
            command="git diff --stat",
            client_session_id="session-abc",
            trust_scope="session",
            working_directory=r"D:\Projects\Jarvin",
            argv=["git", "diff", "--stat"],
            diff_preview="--- before\n+++ after",
            detail="Trusted for this client session.",
        )

        fetched = action_log.get_agent_action_event(created["id"])

        assert fetched["client_session_id"] == "session-abc"
        assert fetched["trust_scope"] == "session"
        assert fetched["working_directory"] == r"D:\Projects\Jarvin"
        assert fetched["argv"] == ["git", "diff", "--stat"]
        assert fetched["diff_preview"] is not None
        assert fetched["diff_preview"].startswith("--- before")
    finally:
        action_log._reset_for_tests()
