from __future__ import annotations

from backend.agent.voice import voice_listener_clarification_state as listener_review_mod
from backend.agent.voice.voice_transcription_review import VoiceTranscriptionReviewResult


def test_listener_voice_review_confirms_then_accepts_yes(monkeypatch):
    listener_review_mod.clear_listener_voice_review_state()
    monkeypatch.setattr(
        listener_review_mod,
        "review_remote_transcription",
        lambda text: VoiceTranscriptionReviewResult(
            confidence_level="medium",
            confidence_score=0.62,
            action="confirm",
            suggested_text="Burnaby near Metrotown",
            clarification_message=f'I heard "{text}". Did you mean "Burnaby near Metrotown"?',
        ),
    )

    initial = listener_review_mod.resolve_listener_voice_review("Burnaby by Metro Hound")
    follow_up = listener_review_mod.resolve_listener_voice_review("yes")

    assert initial.review_action == "confirm"
    assert initial.acted_text is None
    assert "Did you mean" in (initial.spoken_reply or "")
    assert follow_up.review_action == "accept"
    assert follow_up.acted_text == "Burnaby near Metrotown"
    assert follow_up.should_persist_turn is True


def test_listener_voice_review_repeat_blocks_action(monkeypatch):
    listener_review_mod.clear_listener_voice_review_state()
    monkeypatch.setattr(
        listener_review_mod,
        "review_remote_transcription",
        lambda _text: VoiceTranscriptionReviewResult(
            confidence_level="low",
            confidence_score=0.2,
            action="repeat",
            clarification_message="Please repeat that clearly.",
        ),
    )

    decision = listener_review_mod.resolve_listener_voice_review("Waken-ez")

    assert decision.review_action == "repeat"
    assert decision.acted_text is None
    assert decision.spoken_reply == "Please repeat that clearly."
