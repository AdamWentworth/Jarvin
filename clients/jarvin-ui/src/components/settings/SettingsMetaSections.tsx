import type { FormEvent } from "react";
import {
  COMMUNICATION_STYLE_OPTIONS,
  MOOD_OPTIONS,
  RESPONSE_LENGTH_OPTIONS,
} from "../../lib/ui";
import { stageLabel } from "../../lib/runtime";
import type { SettingsOverlayProps } from "./SettingsOverlay.types";

type ProfileSectionProps = Pick<
  SettingsOverlayProps,
  "onProfileChange" | "onSaveProfile" | "profile" | "profileStatus"
>;

type DiagnosticsSectionProps = Pick<
  SettingsOverlayProps,
  | "agentActionLog"
  | "agentActionLogStatus"
  | "connectionState"
  | "connectionSummary"
  | "currentListenerStatus"
  | "health"
  | "isClientOnline"
  | "lastConnectionError"
  | "lastRoundTripMs"
  | "lastSuccessfulContactLabel"
  | "live"
  | "onRefreshAgentActionLog"
  | "remoteVoiceDiagnostics"
>;

export function SettingsProfileSection({
  onProfileChange,
  onSaveProfile,
  profile,
  profileStatus,
}: ProfileSectionProps) {
  return (
    <section className="inspector-panel-body">
      <div className="section-copy">
        <h3>Profile and personalization</h3>
        <p>These preferences live on the host so every client gets the same assistant behavior.</p>
      </div>

      <form className="profile-grid" onSubmit={onSaveProfile as (event: FormEvent<HTMLFormElement>) => void}>
        <label className="field-stack">
          <span>Name</span>
          <input
            value={profile.name}
            onChange={(event) => onProfileChange((current) => ({ ...current, name: event.currentTarget.value }))}
            placeholder="Your name"
          />
        </label>

        <label className="field-stack">
          <span>Goal</span>
          <input
            value={profile.goal}
            onChange={(event) => onProfileChange((current) => ({ ...current, goal: event.currentTarget.value }))}
            placeholder="Current goal"
          />
        </label>

        <label className="field-stack">
          <span>Mood</span>
          <select
            value={profile.mood}
            onChange={(event) => onProfileChange((current) => ({ ...current, mood: event.currentTarget.value }))}
          >
            {MOOD_OPTIONS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>

        <label className="field-stack">
          <span>Communication style</span>
          <select
            value={profile.communication_style}
            onChange={(event) =>
              onProfileChange((current) => ({ ...current, communication_style: event.currentTarget.value }))
            }
          >
            {COMMUNICATION_STYLE_OPTIONS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>

        <label className="field-stack">
          <span>Response length</span>
          <select
            value={profile.response_length}
            onChange={(event) =>
              onProfileChange((current) => ({ ...current, response_length: event.currentTarget.value }))
            }
          >
            {RESPONSE_LENGTH_OPTIONS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>

        <div className="button-row">
          <button type="submit" className="primary-button">
            Save profile
          </button>
        </div>
      </form>

      <p className="section-status">{profileStatus || "Saved profile preferences will live on the host."}</p>
    </section>
  );
}

export function SettingsDiagnosticsSection({
  agentActionLog,
  agentActionLogStatus,
  connectionState,
  connectionSummary,
  currentListenerStatus,
  health,
  isClientOnline,
  lastConnectionError,
  lastRoundTripMs,
  lastSuccessfulContactLabel,
  live,
  onRefreshAgentActionLog,
  remoteVoiceDiagnostics,
}: DiagnosticsSectionProps) {
  return (
    <section className="inspector-panel-body">
      <div className="section-copy">
        <h3>Diagnostics</h3>
        <p>Low-level state stays available here without crowding the main settings flow.</p>
      </div>

      <section className="nested-panel">
        <div className="section-copy">
          <h3>Host and client state</h3>
        </div>

        <div className="overview-grid diagnostic-grid">
          <div className="overview-stat">
            <span>Host connection</span>
            <strong>{connectionSummary} | {connectionState}</strong>
          </div>
          <div className="overview-stat">
            <span>Last contact</span>
            <strong>{lastSuccessfulContactLabel}</strong>
          </div>
          <div className="overview-stat">
            <span>Latency</span>
            <strong>{lastRoundTripMs !== null ? `${lastRoundTripMs} ms` : "Waiting for ping"}</strong>
          </div>
          <div className="overview-stat">
            <span>Client network</span>
            <strong>{isClientOnline ? "Online" : "Offline"}</strong>
          </div>
          <div className="overview-stat">
            <span>Health probe</span>
            <strong>{health ? `${health.status} | listener ${health.listening ? "up" : "down"}` : "Unknown"}</strong>
          </div>
          <div className="overview-stat">
            <span>Listener state</span>
            <strong>{currentListenerStatus}</strong>
          </div>
          <div className="overview-stat">
            <span>Last transcript</span>
            <strong>{live?.transcript || "None yet"}</strong>
          </div>
          <div className="overview-stat">
            <span>Last reply</span>
            <strong>{live?.reply || "None yet"}</strong>
          </div>
          <div className="overview-stat">
            <span>Timing</span>
            <strong>
              {live?.cycle_ms ? `${live.cycle_ms} ms cycle` : "Waiting for activity"}
              {live?.utter_ms ? ` | ${live.utter_ms} ms utterance` : ""}
            </strong>
          </div>
        </div>
      </section>

      <section className="nested-panel">
        <div className="section-copy">
          <h3>Remote voice pipeline</h3>
        </div>

        <div className="overview-grid diagnostic-grid">
          <div className="overview-stat">
            <span>Mic capture</span>
            <strong>{stageLabel(remoteVoiceDiagnostics.microphone)}</strong>
          </div>
          <div className="overview-stat">
            <span>Upload</span>
            <strong>{stageLabel(remoteVoiceDiagnostics.upload)}</strong>
          </div>
          <div className="overview-stat">
            <span>Transcription</span>
            <strong>{stageLabel(remoteVoiceDiagnostics.transcription)}</strong>
          </div>
          <div className="overview-stat">
            <span>Chat round-trip</span>
            <strong>{stageLabel(remoteVoiceDiagnostics.chat)}</strong>
          </div>
          <div className="overview-stat">
            <span>Reply playback</span>
            <strong>{stageLabel(remoteVoiceDiagnostics.playback)}</strong>
          </div>
          <div className="overview-stat">
            <span>Last voice note</span>
            <strong>{remoteVoiceDiagnostics.note || lastConnectionError || "No recent remote voice events."}</strong>
          </div>
        </div>
      </section>

      <section className="nested-panel">
        <div className="section-copy">
          <h3>Host action log</h3>
          <p>Recent risky host actions, approvals, trust grants, and execution results.</p>
        </div>

        <div className="button-row">
          <button type="button" className="ghost-button" onClick={onRefreshAgentActionLog}>
            Refresh action log
          </button>
        </div>

        {agentActionLogStatus ? <p className="section-status">{agentActionLogStatus}</p> : null}

        {agentActionLog.length ? (
          <div className="diagnostic-log-list">
            {agentActionLog.map((item) => (
              <article key={item.id} className="diagnostic-log-card">
                <div className="diagnostic-log-header">
                  <strong>{item.title}</strong>
                  <span>{new Date(item.created_at).toLocaleString()}</span>
                </div>
                <p className="diagnostic-log-summary">{item.summary}</p>
                <p className="diagnostic-log-meta">
                  {item.event_kind} | {item.action_kind} | {item.risk_level} | {item.access_mode}
                </p>
                {item.trust_scope ? <p className="diagnostic-log-meta">Trust scope: {item.trust_scope}</p> : null}
                {item.working_directory ? <p className="diagnostic-log-meta">CWD: {item.working_directory}</p> : null}
                {item.argv?.length ? <p className="diagnostic-log-meta">Args: {item.argv.join(" | ")}</p> : null}
                {item.command ? <p className="diagnostic-log-meta">Command: {item.command}</p> : null}
                {item.path ? <p className="diagnostic-log-meta">Path: {item.path}</p> : null}
                {item.content_preview ? <p className="diagnostic-log-meta">Preview: {item.content_preview}</p> : null}
                {item.diff_preview ? (
                  <pre className="approval-request-preview diagnostic-log-preview">
                    <code>{item.diff_preview}</code>
                  </pre>
                ) : null}
                {item.detail ? <p className="diagnostic-log-meta">{item.detail}</p> : null}
              </article>
            ))}
          </div>
        ) : (
          <p className="section-status">No risky host actions have been recorded yet.</p>
        )}
      </section>
    </section>
  );
}
