from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .voice_transcription_review import review_remote_transcription

_YES_WORDS = {"yes", "yeah", "yep", "correct", "exactly", "that one", "do that", "use that"}
_NO_WORDS = {"no", "nope", "cancel", "never mind", "nevermind", "wrong"}


@dataclass(frozen=True)
class ListenerVoiceReviewDecision:
    acted_text: str | None = None
    spoken_reply: str | None = None
    transcript_for_display: str | None = None
    should_persist_turn: bool = False
    review_action: str = "accept"


@dataclass
class _PendingListenerVoiceReview:
    original_text: str
    candidate_text: str
    clarification_message: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(seconds=45))


_pending_listener_review: _PendingListenerVoiceReview | None = None


def resolve_listener_voice_review(text: str) -> ListenerVoiceReviewDecision:
    cleaned = " ".join(str(text or "").strip().split())
    if not cleaned:
        return ListenerVoiceReviewDecision(
            acted_text=None,
            spoken_reply="I did not catch that clearly. Please try again.",
            transcript_for_display=None,
            should_persist_turn=False,
            review_action="repeat",
        )

    pending = _get_pending_review()
    if pending is not None:
        lower = cleaned.lower()
        if lower in _YES_WORDS:
            _clear_pending_review()
            return ListenerVoiceReviewDecision(
                acted_text=pending.candidate_text,
                spoken_reply=None,
                transcript_for_display=pending.candidate_text,
                should_persist_turn=True,
                review_action="accept",
            )
        if lower in _NO_WORDS:
            _clear_pending_review()
            return ListenerVoiceReviewDecision(
                acted_text=None,
                spoken_reply="Okay, please say it again in a different way.",
                transcript_for_display=cleaned,
                should_persist_turn=False,
                review_action="repeat",
            )

    review = review_remote_transcription(cleaned)
    candidate_text = (review.suggested_text or "").strip() or cleaned

    if review.action == "accept":
        _clear_pending_review()
        return ListenerVoiceReviewDecision(
            acted_text=candidate_text,
            spoken_reply=None,
            transcript_for_display=candidate_text,
            should_persist_turn=True,
            review_action="accept",
        )

    if review.action == "confirm":
        _set_pending_review(
            original_text=cleaned,
            candidate_text=candidate_text,
            clarification_message=review.clarification_message
            or f'I heard "{cleaned}". Did you mean "{candidate_text}"?',
        )
        return ListenerVoiceReviewDecision(
            acted_text=None,
            spoken_reply=_pending_listener_review.clarification_message if _pending_listener_review else review.clarification_message,
            transcript_for_display=cleaned,
            should_persist_turn=False,
            review_action="confirm",
        )

    _clear_pending_review()
    return ListenerVoiceReviewDecision(
        acted_text=None,
        spoken_reply=review.clarification_message or "That did not sound reliable enough to act on. Please repeat it.",
        transcript_for_display=cleaned,
        should_persist_turn=False,
        review_action="repeat",
    )


def clear_listener_voice_review_state() -> None:
    _clear_pending_review()


def _get_pending_review() -> _PendingListenerVoiceReview | None:
    global _pending_listener_review
    pending = _pending_listener_review
    if pending is None:
        return None
    if pending.expires_at <= datetime.now(timezone.utc):
        _pending_listener_review = None
        return None
    return pending


def _set_pending_review(*, original_text: str, candidate_text: str, clarification_message: str) -> None:
    global _pending_listener_review
    _pending_listener_review = _PendingListenerVoiceReview(
        original_text=original_text,
        candidate_text=candidate_text,
        clarification_message=clarification_message,
    )


def _clear_pending_review() -> None:
    global _pending_listener_review
    _pending_listener_review = None
