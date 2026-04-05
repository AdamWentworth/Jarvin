import type { TaskRequestToolPayload } from "../lib/types";

type TaskRequestCardProps = {
  payload: TaskRequestToolPayload;
  sending: boolean;
  onApprove: () => void;
  onDeny: () => void;
};

function statusLabel(value: string): string {
  if (value === "blocked") {
    return "Blocked";
  }
  if (value === "denied") {
    return "Denied";
  }
  if (value === "running") {
    return "Running";
  }
  if (value === "completed") {
    return "Completed";
  }
  if (value === "failed") {
    return "Failed";
  }
  return "Ready";
}

function riskLabel(value: string): string {
  if (value === "high") {
    return "High risk";
  }
  if (value === "medium") {
    return "Medium risk";
  }
  return "Low risk";
}

export function TaskRequestCard({ payload, sending, onApprove, onDeny }: TaskRequestCardProps) {
  return (
    <section className={`task-request-card status-${payload.status || "pending"}`}>
      <header className="task-request-header">
        <div className="task-request-copy">
          <strong>{payload.title || "Host task"}</strong>
          <span>{payload.summary}</span>
        </div>

        <div className="approval-request-badges">
          <span className={`approval-badge risk-${payload.risk_level || "low"}`}>{riskLabel(payload.risk_level || "")}</span>
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

      {payload.steps?.length ? (
        <ol className="task-step-list">
          {payload.steps.map((step) => (
            <li key={step.step_id} className={`task-step-card status-${step.status || "pending"}`}>
              <div className="task-step-header">
                <strong>{step.title}</strong>
                <span>{statusLabel(step.status || "")}</span>
              </div>
              <p className="task-step-meta">
                {step.action_kind}
                {step.path ? ` | ${step.path}` : ""}
                {step.query ? ` | ${step.query}` : ""}
                {step.command ? ` | ${step.command}` : ""}
              </p>
              {step.detail ? <p className="task-step-detail">{step.detail}</p> : null}
              {step.preview_block ? (
                <pre className="approval-request-preview">
                  <code>{step.preview_block}</code>
                </pre>
              ) : null}
            </li>
          ))}
        </ol>
      ) : null}

      <div className="approval-request-footer">
        {payload.can_approve ? (
          <div className="approval-request-actions">
            <button type="button" className="primary-button" onClick={onApprove} disabled={sending}>
              Approve task
            </button>
            <button type="button" className="ghost-button" onClick={onDeny} disabled={sending}>
              Deny
            </button>
          </div>
        ) : (
          <p className="approval-request-meta">
            {payload.status === "blocked"
              ? "This task needs broader host access than the current client mode allows."
              : `Progress: ${payload.completed_steps ?? 0} / ${payload.total_steps ?? payload.steps?.length ?? 0} steps complete.`}
          </p>
        )}
      </div>
    </section>
  );
}
