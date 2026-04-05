import type { PendingVoiceReview } from "../lib/runtime";

type VoiceTranscriptionReviewCardProps = {
  review: PendingVoiceReview;
  sending: boolean;
  onUseSuggestion: () => void;
  onSendHeard: () => void;
  onRetry: () => void;
  onDismiss: () => void;
};

export function VoiceTranscriptionReviewCard({
  review,
  sending,
  onUseSuggestion,
  onSendHeard,
  onRetry,
  onDismiss,
}: VoiceTranscriptionReviewCardProps) {
  const confidencePercent = Math.max(0, Math.min(100, Math.round(review.review.confidence_score * 100)));
  const confidenceLevel = review.review.confidence_level;
  const hasSuggestion =
    Boolean(review.review.suggested_text) && review.review.suggested_text !== review.heardText;

  return (
    <article className={`voice-review-card tone-${confidenceLevel}`}>
      <header className="voice-review-header">
        <div>
          <div className="voice-review-eyebrow">Voice check</div>
          <h3>Let me verify that before I act on it</h3>
        </div>
        <div className={`voice-review-badge level-${confidenceLevel}`}>{confidenceLevel}</div>
      </header>

      <div className="voice-review-gauge-shell" aria-label={`Voice confidence ${confidencePercent}%`}>
        <div className="voice-review-gauge-track">
          <div className={`voice-review-gauge-fill level-${confidenceLevel}`} style={{ width: `${confidencePercent}%` }} />
        </div>
        <span>{confidencePercent}% confidence</span>
      </div>

      <p className="voice-review-message">
        {review.review.clarification_message || 'This transcript looks shaky enough that I want to check it first.'}
      </p>

      <div className="voice-review-copy">
        <div className="voice-review-field">
          <span className="voice-review-label">Heard</span>
          <p>{review.heardText}</p>
        </div>
        {hasSuggestion ? (
          <div className="voice-review-field suggested">
            <span className="voice-review-label">Suggested</span>
            <p>{review.review.suggested_text}</p>
          </div>
        ) : null}
      </div>

      {review.review.review_reason ? <p className="voice-review-reason">{review.review.review_reason}</p> : null}

      <div className="voice-review-actions">
        {hasSuggestion ? (
          <button type="button" className="primary-button compact-button" onClick={onUseSuggestion} disabled={sending}>
            Use suggestion
          </button>
        ) : null}
        <button type="button" className="secondary-button compact-button" onClick={onSendHeard} disabled={sending}>
          Send as heard
        </button>
        <button type="button" className="ghost-button compact-button" onClick={onRetry} disabled={sending}>
          Try again
        </button>
        <button type="button" className="ghost-button compact-button" onClick={onDismiss} disabled={sending}>
          Dismiss
        </button>
      </div>
    </article>
  );
}
