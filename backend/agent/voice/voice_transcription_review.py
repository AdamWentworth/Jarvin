from __future__ import annotations

import json
import re
from dataclasses import dataclass

from backend.ai_engine import build_jarvin_config, generate_reply

_SHORT_SAFE_EXACT = {
    "yes",
    "yeah",
    "yep",
    "no",
    "nope",
    "cancel",
    "stop",
    "pause",
    "resume",
    "start",
    "send",
    "approve",
    "deny",
    "retry",
    "again",
}

_SHORT_SAFE_PATTERNS = (
    re.compile(r"^(today|tomorrow|tonight)(\b.*)?$", re.IGNORECASE),
    re.compile(r"^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)(\b.*)?$", re.IGNORECASE),
    re.compile(r"^(at\s+)?\d{1,2}(:\d{2})?\s*(am|pm)?$", re.IGNORECASE),
    re.compile(r"^(in|after|before)\s+.+$", re.IGNORECASE),
)


@dataclass(frozen=True)
class VoiceTranscriptionReviewResult:
    confidence_level: str = "high"
    confidence_score: float = 1.0
    action: str = "accept"
    suggested_text: str | None = None
    clarification_message: str | None = None
    review_reason: str | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "confidence_level": self.confidence_level,
            "confidence_score": self.confidence_score,
            "action": self.action,
            "suggested_text": self.suggested_text,
            "clarification_message": self.clarification_message,
            "review_reason": self.review_reason,
        }


def review_remote_transcription(text: str) -> VoiceTranscriptionReviewResult:
    cleaned = _normalize_text(text)
    if not cleaned:
        return VoiceTranscriptionReviewResult(
            confidence_level="low",
            confidence_score=0.05,
            action="repeat",
            clarification_message="I did not catch enough speech to act on that. Please try again.",
            review_reason="No usable transcript text was available.",
        )

    heuristic_review = _heuristic_review(cleaned)
    if heuristic_review is not None:
        return heuristic_review

    cfg_obj = build_jarvin_config(
        mode="agent_strong",
        system_instructions=_review_system_prompt(),
        temperature=0.1,
        max_tokens=220,
    )
    prompt = f"User speech transcript:\n{cleaned}"

    try:
        raw = generate_reply(prompt, cfg=cfg_obj, context=None)
    except Exception:
        return _fallback_review(cleaned)

    data = _parse_json_object(raw)
    if not data:
        return _fallback_review(cleaned)

    confidence_level = _normalize_confidence_level(data.get("confidence_level"))
    confidence_score = _normalize_confidence_score(data.get("confidence_score"), confidence_level)
    action = _normalize_action(data.get("action"), confidence_level)
    suggested_text = _clean_optional_text(data.get("suggested_text"))
    clarification_message = _clean_optional_text(data.get("clarification_message"))
    review_reason = _clean_optional_text(data.get("review_reason"))
    suggested_text = _sanitize_suggested_text(suggested_text, original_text=cleaned)
    confidence_level, confidence_score = _harmonize_confidence(
        action=action,
        confidence_level=confidence_level,
        confidence_score=confidence_score,
    )

    if action == "accept" and suggested_text == cleaned:
        suggested_text = None

    if action == "confirm" and clarification_message is None:
        if suggested_text and suggested_text != cleaned:
            clarification_message = f'I heard "{cleaned}". Did you mean "{suggested_text}"?'
        else:
            clarification_message = f'I heard "{cleaned}". Does that look right before I act on it?'

    if action == "repeat" and clarification_message is None:
        clarification_message = "That transcription does not look reliable enough to act on. Please repeat it."

    return VoiceTranscriptionReviewResult(
        confidence_level=confidence_level,
        confidence_score=confidence_score,
        action=action,
        suggested_text=suggested_text,
        clarification_message=clarification_message,
        review_reason=review_reason,
    )


def _review_system_prompt() -> str:
    return (
        "You review speech-to-text transcriptions before Jarvin acts on them. "
        "Return JSON only with keys: confidence_level, confidence_score, action, suggested_text, "
        "clarification_message, review_reason. "
        "Valid confidence_level values: high, medium, low. "
        "Valid action values: accept, confirm, repeat. "
        "Use accept when the transcript is clear enough to act on as-is. "
        "Use confirm when the transcript is understandable but suspicious, garbled, or probably misheard, "
        "especially for location names, app names, or odd phrases. If you can plausibly repair it, set suggested_text. "
        "Use repeat when the transcript is too incoherent to trust. "
        "Do not over-correct quirky but coherent requests. Fragments like 'tomorrow at 5', 'yes', 'no', "
        "'cancel', or short follow-up timing phrases can still be valid and should usually be accepted. "
        "Never answer the user's request. Only judge transcript reliability."
    )


def _heuristic_review(text: str) -> VoiceTranscriptionReviewResult | None:
    lowered = text.lower()
    if lowered in _SHORT_SAFE_EXACT:
        return VoiceTranscriptionReviewResult(
            confidence_level="high",
            confidence_score=0.96,
            action="accept",
            clarification_message=None,
            review_reason="Short confirmation-style voice reply.",
        )
    for pattern in _SHORT_SAFE_PATTERNS:
        if pattern.match(text):
            return VoiceTranscriptionReviewResult(
                confidence_level="high",
                confidence_score=0.9,
                action="accept",
                clarification_message=None,
                review_reason="Short contextual follow-up that is still a valid instruction fragment.",
            )
    if len(text.split()) == 1 and len(text) >= 4:
        return VoiceTranscriptionReviewResult(
            confidence_level="medium",
            confidence_score=0.56,
            action="confirm",
            suggested_text=text,
            clarification_message=f'I heard "{text}". Does that look right before I act on it?',
            review_reason="Single-word transcript could be a valid follow-up, but it is easy for ASR to mangle.",
        )
    return None


def _fallback_review(text: str) -> VoiceTranscriptionReviewResult:
    word_count = len(text.split())
    if word_count <= 1:
        return VoiceTranscriptionReviewResult(
            confidence_level="medium",
            confidence_score=0.55,
            action="confirm",
            suggested_text=text,
            clarification_message=f'I heard "{text}". Does that look right before I act on it?',
            review_reason="Fallback review is cautious with very short transcripts.",
        )
    return VoiceTranscriptionReviewResult(
        confidence_level="high",
        confidence_score=0.82,
        action="accept",
        clarification_message=None,
        review_reason="Fallback review accepted a multi-word transcript when semantic review was unavailable.",
    )


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def _normalize_confidence_level(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"high", "medium", "low"}:
        return normalized
    return "medium"


def _normalize_confidence_score(value: object, confidence_level: str) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        defaults = {"high": 0.9, "medium": 0.6, "low": 0.25}
        return defaults.get(confidence_level, 0.6)
    return max(0.0, min(1.0, score))


def _normalize_action(value: object, confidence_level: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"accept", "confirm", "repeat"}:
        return normalized
    if confidence_level == "high":
        return "accept"
    if confidence_level == "low":
        return "repeat"
    return "confirm"


def _clean_optional_text(value: object) -> str | None:
    cleaned = str(value or "").strip()
    return cleaned or None


def _sanitize_suggested_text(value: str | None, *, original_text: str) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if cleaned.lower().startswith("user speech transcript:"):
        cleaned = cleaned.split(":", 1)[1].strip()
    if not cleaned or cleaned == original_text:
        return None
    if _looks_meta_suggestion(cleaned):
        return None
    if _normalize_for_equivalence(cleaned) == _normalize_for_equivalence(original_text):
        return None
    return cleaned


def _harmonize_confidence(*, action: str, confidence_level: str, confidence_score: float) -> tuple[str, float]:
    if action == "accept":
        level = "high" if confidence_level == "low" else confidence_level
        score = max(confidence_score, 0.78)
        return level, score
    if action == "confirm":
        score = min(max(confidence_score, 0.42), 0.74)
        return "medium", score
    score = min(confidence_score, 0.38)
    return "low", score


def _normalize_for_equivalence(text: str) -> str:
    normalized = str(text or "").strip().lower()
    normalized = re.sub(r"^(hey\s+jarv(?:in|an|is)[,:\s-]*)", "", normalized)
    normalized = re.sub(r"[^\w\s]", "", normalized)
    normalized = " ".join(normalized.split())
    return normalized


def _looks_meta_suggestion(text: str) -> bool:
    lowered = text.lower()
    meta_phrases = (
        "please clarify",
        "provide more context",
        "user requested",
        "the user",
        "cannot be acted on",
        "cannot be executed",
        "looks unclear",
    )
    return any(phrase in lowered for phrase in meta_phrases)


def _parse_json_object(text: str) -> dict[str, object]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
