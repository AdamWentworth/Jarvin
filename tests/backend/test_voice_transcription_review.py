from __future__ import annotations

from backend.agent.voice import voice_transcription_review as review_mod


def test_review_remote_transcription_accepts_short_follow_up():
    review = review_mod.review_remote_transcription("tomorrow at 5pm")

    assert review.action == "accept"
    assert review.confidence_level == "high"


def test_review_remote_transcription_accepts_coherent_multiword_request_without_llm(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise AssertionError("LLM review should not run for a coherent request.")

    monkeypatch.setattr(review_mod, "generate_reply", _boom)

    review = review_mod.review_remote_transcription(
        "Please output all of my reminders and anything else in my calendar."
    )

    assert review.action == "accept"
    assert review.confidence_level == "high"
    assert "coherent spoken request" in (review.review_reason or "")


def test_review_remote_transcription_accepts_coherent_followup_without_llm(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise AssertionError("LLM review should not run for a coherent follow-up.")

    monkeypatch.setattr(review_mod, "generate_reply", _boom)

    review = review_mod.review_remote_transcription("I was thinking of going to Costco around 12 noon.")

    assert review.action == "accept"
    assert review.confidence_level == "high"


def test_review_remote_transcription_uses_llm_json_for_confirmation(monkeypatch):
    monkeypatch.setattr(
        review_mod,
        "generate_reply",
        lambda *_args, **_kwargs: (
            '{"confidence_level":"medium","confidence_score":0.41,"action":"confirm",'
            '"suggested_text":"Burnaby near Metrotown",'
            '"clarification_message":"I heard \\"Burnaby by Metro Hound\\". Did you mean \\"Burnaby near Metrotown\\"?",'
            '"review_reason":"The location name looks garbled."}'
        ),
    )

    review = review_mod.review_remote_transcription("Burnaby by Metro Hound near station")

    assert review.action == "confirm"
    assert review.suggested_text == "Burnaby near Metrotown"
    assert "garbled" in (review.review_reason or "")


def test_review_remote_transcription_confirms_ambiguous_short_phrase_without_llm(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise AssertionError("LLM review should not run for a short ambiguous phrase.")

    monkeypatch.setattr(review_mod, "generate_reply", _boom)

    review = review_mod.review_remote_transcription("Burnaby by Metro Hound")

    assert review.action == "confirm"
    assert review.confidence_level == "medium"
    assert review.suggested_text == "Burnaby by Metro Hound"


def test_review_remote_transcription_falls_back_to_confirm_for_single_word(monkeypatch):
    monkeypatch.setattr(review_mod, "generate_reply", lambda *_args, **_kwargs: "")

    review = review_mod.review_remote_transcription("Waken-ez")

    assert review.action == "confirm"
    assert review.confidence_level == "medium"
    assert review.suggested_text == "Waken-ez"
