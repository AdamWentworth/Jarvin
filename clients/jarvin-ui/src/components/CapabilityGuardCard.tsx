import { ShieldExclamationIcon } from "@heroicons/react/20/solid";
import type { CapabilityGuardToolPayload } from "../lib/types";

type CapabilityGuardCardProps = {
  payload: CapabilityGuardToolPayload;
};

function domainLabel(domain: string): string {
  if (domain === "organizer") {
    return "Calendar + reminders";
  }
  return domain ? `${domain[0].toUpperCase()}${domain.slice(1)}` : "Managed action";
}

export function CapabilityGuardCard({ payload }: CapabilityGuardCardProps) {
  return (
    <aside className="capability-guard-card" aria-label="Verified capability boundary">
      <div className="capability-guard-header">
        <span className="capability-guard-icon" aria-hidden="true">
          <ShieldExclamationIcon />
        </span>
        <div className="capability-guard-copy">
          <strong>No action performed</strong>
          <span>{payload.explanation}</span>
        </div>
        <span className="capability-guard-domain">{domainLabel(payload.domain)}</span>
      </div>

      {payload.examples.length > 0 ? (
        <div className="capability-guard-examples">
          <span>Try an explicit request:</span>
          <ul>
            {payload.examples.map((example) => (
              <li key={example}>{example}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </aside>
  );
}
