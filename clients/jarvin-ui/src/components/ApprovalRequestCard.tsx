import type { ApprovalRequestToolPayload } from "../lib/types";

type ApprovalRequestCardProps = {
  payload: ApprovalRequestToolPayload;
  sending: boolean;
  onApprove: () => void;
  onDeny: () => void;
};

function accessModeLabel(value: string): string {
  if (value === "full_access") {
    return "Trusted full access";
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
  return "Needs approval";
}

function riskLabel(value: string): string {
  return value === "high" ? "High risk" : "Medium risk";
}

export function ApprovalRequestCard({ payload, sending, onApprove, onDeny }: ApprovalRequestCardProps) {
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

      <div className="approval-request-footer">
        <p className="approval-request-meta">Client access: {accessModeLabel(payload.access_mode || "")}</p>

        {payload.can_approve ? (
          <div className="approval-request-actions">
            <button type="button" className="primary-button" onClick={onApprove} disabled={sending}>
              Approve
            </button>
            <button type="button" className="ghost-button" onClick={onDeny} disabled={sending}>
              Deny
            </button>
          </div>
        ) : (
          <p className="approval-request-meta">Change Agent access in Settings to allow this kind of host action from this client.</p>
        )}
      </div>
    </section>
  );
}
