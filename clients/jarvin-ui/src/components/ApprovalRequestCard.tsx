import type { ApprovalRequestToolPayload } from "../lib/types";

type ApprovalRequestCardProps = {
  payload: ApprovalRequestToolPayload;
  sending: boolean;
  onApprove: () => void;
  onDeny: () => void;
  onTrustConversation: () => void;
  onTrustSession: () => void;
};

function accessModeLabel(value: string): string {
  if (value === "full_access") {
    return "Trusted host tool access";
  }
  if (value === "read_only") {
    return "Read only";
  }
  return "Approve risky actions";
}

function statusLabel(value: string): string {
  if (value === "blocked") {
    return "Blocked";
  }
  if (value === "denied") {
    return "Denied";
  }
  if (value === "approved") {
    return "Approved";
  }
  if (value === "trusted") {
    return "Trusted";
  }
  return "Needs approval";
}

function riskLabel(value: string): string {
  return value === "high" ? "High risk" : "Medium risk";
}

export function ApprovalRequestCard({
  payload,
  sending,
  onApprove,
  onDeny,
  onTrustConversation,
  onTrustSession,
}: ApprovalRequestCardProps) {
  return (
    <section className={`approval-request-card status-${payload.status || "pending"}`}>
      <header className="approval-request-header">
        <div className="approval-request-copy">
          <strong>{payload.title || "Host action request"}</strong>
          <span>{payload.summary}</span>
        </div>

        <div className="approval-request-badges">
          <span className={`approval-badge risk-${payload.risk_level || "medium"}`}>{riskLabel(payload.risk_level || "")}</span>
          <span className={`approval-badge status-${payload.status || "pending"}`}>{statusLabel(payload.status || "")}</span>
        </div>
      </header>

      {payload.details?.length ? (
        <ul className="approval-request-details">
          {payload.details.map((detail) => (
            <li key={detail}>{detail}</li>
          ))}
        </ul>
      ) : null}

      {payload.preview_block ? (
        <pre className="approval-request-preview">
          <code>{payload.preview_block}</code>
        </pre>
      ) : null}

      <div className="approval-request-footer">
        <p className="approval-request-meta">Client access: {accessModeLabel(payload.access_mode || "")}</p>

        {payload.can_approve ? (
          <div className="approval-request-actions">
            <button type="button" className="primary-button" onClick={onApprove} disabled={sending}>
              Approve once
            </button>
            {payload.can_trust_conversation ? (
              <button type="button" className="secondary-button" onClick={onTrustConversation} disabled={sending}>
                Trust this chat
              </button>
            ) : null}
            {payload.can_trust_session ? (
              <button type="button" className="secondary-button" onClick={onTrustSession} disabled={sending}>
                Trust this session
              </button>
            ) : null}
            <button type="button" className="ghost-button" onClick={onDeny} disabled={sending}>
              Deny
            </button>
          </div>
        ) : (
          <p className="approval-request-meta">
            {payload.trust_active
              ? `Similar host actions in this ${payload.trust_scope === "session" ? "session" : "conversation"} can keep running without another approval prompt for a while.`
              : "Change Agent access in Settings to allow this kind of host action from this client."}
          </p>
        )}
      </div>
    </section>
  );
}
