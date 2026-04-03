from __future__ import annotations

import backend.ai_engine as ai


def test_build_jarvin_config_uses_agent_preset():
    cfg = ai.build_jarvin_config(mode="agent_strong")

    assert cfg.mode == "agent_strong"
    assert cfg.max_tokens == 512
    assert cfg.max_sentences is None
    assert cfg.history_window == 8


def test_generate_reply_voice_fast_clips_to_short_response(monkeypatch):
    monkeypatch.setattr(
        ai,
        "chat_completion",
        lambda **kwargs: "First sentence. Second sentence. Third sentence.",
        raising=True,
    )

    out = ai.generate_reply("hello", cfg=ai.build_jarvin_config(mode="voice_fast"))

    assert out == "First sentence. Second sentence."


def test_generate_reply_agent_strong_preserves_structured_output(monkeypatch):
    monkeypatch.setattr(
        ai,
        "chat_completion",
        lambda **kwargs: "Plan:\n- Step one\n- Step two\n- Step three",
        raising=True,
    )

    out = ai.generate_reply("plan this", cfg=ai.build_jarvin_config(mode="agent_strong"))

    assert "- Step one" in out
    assert "- Step two" in out
