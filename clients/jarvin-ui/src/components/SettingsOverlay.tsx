import type { FormEvent, MouseEvent } from "react";
import type { AudioDevicesResponse, HealthResponse, LLMOptionsResponse, LiveSnapshot, UserProfilePayload } from "../lib/types";
import {
  COMMUNICATION_STYLE_OPTIONS,
  INSPECTOR_SECTIONS,
  MOOD_OPTIONS,
  RESPONSE_LENGTH_OPTIONS,
  type InspectorSection,
} from "../lib/ui";
import { stageLabel, type ConnectionState, type RemoteVoiceDiagnostics } from "../lib/runtime";

type SettingsOverlayProps = {
  isOpen: boolean;
  onClose: () => void;
  apiBaseUrl: string;
  apiBaseUrlDraft: string;
  onApiBaseUrlDraftChange: (value: string) => void;
  onSaveApiBaseUrl: () => void;
  onClearApiBaseUrl: () => void;
  apiBaseUrlStatus: string;
  currentListenerStatus: string;
  currentModel: string;
  currentBackend: string;
  activeInspectorSection: InspectorSection;
  onSectionChange: (section: InspectorSection) => void;
  onRefreshWorkspace: () => void;
  onReconnectHost: () => void;
  llmOptions: LLMOptionsResponse | null;
  selectedBackend: string;
  selectedModel: string;
  onSelectedBackendChange: (value: string) => void;
  onSelectedModelChange: (value: string) => void;
  onRefreshLlmSettings: () => void;
  onApplyLlmSettings: () => void;
  llmStatus: string;
  audioDevices: AudioDevicesResponse | null;
  selectedDeviceIndex: number | "";
  onSelectAudioDevice: (index: number) => void;
  onListenerAction: (action: "start" | "stop" | "shutdown") => void;
  isListening: boolean;
  deviceStatus: string;
  remoteVoiceAvailable: boolean;
  remoteVoiceDisabledReason: string;
  remoteVoiceStatus: string;
  isRemoteRecording: boolean;
  isRemoteTranscribing: boolean;
  onToggleRemoteVoice: () => void;
  speakRepliesOnThisDevice: boolean;
  onToggleSpeakRepliesOnThisDevice: () => void;
  replyAudioStatus: string;
  latestReplyAudioReady: boolean;
  isReplyAudioPlaying: boolean;
  onPlayLatestReplyAudio: () => void;
  connectionState: ConnectionState;
  connectionSummary: string;
  lastConnectionError: string;
  lastSuccessfulContactLabel: string;
  lastRoundTripMs: number | null;
  isClientOnline: boolean;
  health: HealthResponse | null;
  remoteVoiceDiagnostics: RemoteVoiceDiagnostics;
  profile: UserProfilePayload;
  onProfileChange: (updater: (current: UserProfilePayload) => UserProfilePayload) => void;
  onSaveProfile: (event: FormEvent<HTMLFormElement>) => void;
  profileStatus: string;
  live: LiveSnapshot | null;
};

export function SettingsOverlay({
  isOpen,
  onClose,
  apiBaseUrl,
  apiBaseUrlDraft,
  onApiBaseUrlDraftChange,
  onSaveApiBaseUrl,
  onClearApiBaseUrl,
  apiBaseUrlStatus,
  currentListenerStatus,
  currentModel,
  currentBackend,
  activeInspectorSection,
  onSectionChange,
  onRefreshWorkspace,
  onReconnectHost,
  llmOptions,
  selectedBackend,
  selectedModel,
  onSelectedBackendChange,
  onSelectedModelChange,
  onRefreshLlmSettings,
  onApplyLlmSettings,
  llmStatus,
  audioDevices,
  selectedDeviceIndex,
  onSelectAudioDevice,
  onListenerAction,
  isListening,
  deviceStatus,
  remoteVoiceAvailable,
  remoteVoiceDisabledReason,
  remoteVoiceStatus,
  isRemoteRecording,
  isRemoteTranscribing,
  onToggleRemoteVoice,
  speakRepliesOnThisDevice,
  onToggleSpeakRepliesOnThisDevice,
  replyAudioStatus,
  latestReplyAudioReady,
  isReplyAudioPlaying,
  onPlayLatestReplyAudio,
  connectionState,
  connectionSummary,
  lastConnectionError,
  lastSuccessfulContactLabel,
  lastRoundTripMs,
  isClientOnline,
  health,
  remoteVoiceDiagnostics,
  profile,
  onProfileChange,
  onSaveProfile,
  profileStatus,
  live,
}: SettingsOverlayProps) {
  if (!isOpen) {
    return null;
  }

  const modelChoices =
    selectedBackend === "ollama_http" ? llmOptions?.ollama_model_choices ?? [] : llmOptions?.local_model_choices ?? [];

  function stopBackdropClose(event: MouseEvent<HTMLElement>) {
    event.stopPropagation();
  }

  return (
    <div className="overlay-backdrop" role="presentation" onClick={onClose}>
      <section
        className="settings-overlay"
        role="dialog"
        aria-modal="true"
        aria-label="Jarvin settings"
        onClick={stopBackdropClose}
      >
        <header className="settings-dialog-header">
          <div>
            <div className="eyebrow">Workspace controls</div>
            <h2>Settings</h2>
            <p>All assistant, device, profile, and diagnostic controls live here so the chat surface stays clean.</p>
          </div>

          <div className="settings-dialog-actions">
            <button type="button" className="ghost-button compact-button" onClick={onRefreshWorkspace}>
              Refresh
            </button>
            <button type="button" className="secondary-button compact-button" onClick={onReconnectHost}>
              Reconnect
            </button>
            <button type="button" className="ghost-button compact-button" onClick={onClose}>
              Close
            </button>
          </div>
        </header>

        <div className="settings-dialog-body">
          <section className="nested-panel">
            <div className="section-copy">
              <h3>Host connection</h3>
              <p>The shared client can point at your Jarvin host over WireGuard without rebuilding the app.</p>
            </div>

            <label className="field-stack">
              <span>Host URL</span>
              <input
                value={apiBaseUrlDraft}
                onChange={(event) => onApiBaseUrlDraftChange(event.currentTarget.value)}
                placeholder="http://10.0.0.5:8000"
              />
            </label>

            <div className="button-row">
              <button type="button" className="primary-button" onClick={onSaveApiBaseUrl}>
                Save host
              </button>
              <button type="button" className="ghost-button" onClick={onClearApiBaseUrl}>
                Reset host
              </button>
            </div>

            <p className="section-status">{apiBaseUrlStatus || `Current client target: ${apiBaseUrl}`}</p>
          </section>

          <section className="overview-card">
            <div className="overview-grid">
              <div className="overview-stat">
                <span>Host</span>
                <strong>{apiBaseUrl}</strong>
              </div>
              <div className="overview-stat">
                <span>Connection</span>
                <strong>{connectionSummary}</strong>
              </div>
              <div className="overview-stat">
                <span>Listener</span>
                <strong>{currentListenerStatus}</strong>
              </div>
              <div className="overview-stat">
                <span>Model</span>
                <strong>{currentModel}</strong>
              </div>
              <div className="overview-stat">
                <span>Backend</span>
                <strong>{currentBackend}</strong>
              </div>
            </div>
          </section>

          <div className="inspector-tabs" role="tablist" aria-label="Settings sections">
            {INSPECTOR_SECTIONS.map((section) => (
              <button
                key={section.value}
                type="button"
                role="tab"
                aria-selected={activeInspectorSection === section.value}
                className={`tab-button ${activeInspectorSection === section.value ? "active" : ""}`}
                onClick={() => onSectionChange(section.value)}
              >
                {section.label}
              </button>
            ))}
          </div>

          {activeInspectorSection === "assistant" ? (
            <section className="inspector-panel-body">
              <div className="section-copy">
                <h3>Assistant runtime</h3>
                <p>Model and backend selection stay together in one predictable place.</p>
              </div>

              <div className="field-stack">
                <label>
                  <span>Backend</span>
                  <select value={selectedBackend} onChange={(event) => onSelectedBackendChange(event.currentTarget.value)}>
                    {(llmOptions?.backend_choices ?? []).map((choice) => (
                      <option key={choice.value} value={choice.value}>
                        {choice.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label>
                  <span>Model</span>
                  <select value={selectedModel} onChange={(event) => onSelectedModelChange(event.currentTarget.value)}>
                    {modelChoices.map((choice) => (
                      <option key={choice.value} value={choice.value}>
                        {choice.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="button-row">
                <button type="button" className="secondary-button" onClick={onRefreshLlmSettings}>
                  Refresh models
                </button>
                <button type="button" className="primary-button" onClick={onApplyLlmSettings}>
                  Apply settings
                </button>
              </div>

              <p className="section-status">{llmStatus || "Host model settings will appear here."}</p>
            </section>
          ) : null}

          {activeInspectorSection === "voice" ? (
            <section className="inspector-panel-body">
              <div className="section-copy">
                <h3>Voice modes</h3>
                <p>Jarvin now distinguishes host-room audio from remote client audio so phone access is less confusing.</p>
              </div>

              <section className="nested-panel">
                <div className="section-copy">
                  <h3>Remote client microphone</h3>
                  <p>Use the microphone on this device for push-to-talk input. This is separate from the host machine microphones.</p>
                </div>

                <div className="button-row">
                  <button
                    type="button"
                    className={isRemoteRecording ? "danger-button" : "primary-button"}
                    onClick={onToggleRemoteVoice}
                    disabled={!remoteVoiceAvailable || isRemoteTranscribing}
                    title={remoteVoiceAvailable ? "Use this device microphone" : remoteVoiceDisabledReason}
                  >
                    {isRemoteTranscribing ? "Transcribing..." : isRemoteRecording ? "Stop and send" : "Record from this device"}
                  </button>
                </div>

                <p className="section-status">
                  {remoteVoiceStatus ||
                    (remoteVoiceAvailable
                      ? "Ready to capture audio from this browser or app shell."
                      : remoteVoiceDisabledReason)}
                </p>
              </section>

              <section className="nested-panel">
                <div className="section-copy">
                  <h3>Reply audio on this device</h3>
                  <p>When enabled, Jarvin will synthesize reply audio on the host and play it back through this phone or client.</p>
                </div>

                <div className="button-row">
                  <button
                    type="button"
                    className={speakRepliesOnThisDevice ? "primary-button" : "ghost-button"}
                    onClick={onToggleSpeakRepliesOnThisDevice}
                  >
                    {speakRepliesOnThisDevice ? "Spoken replies enabled" : "Enable spoken replies"}
                  </button>

                  <button
                    type="button"
                    className="secondary-button"
                    onClick={onPlayLatestReplyAudio}
                    disabled={!latestReplyAudioReady}
                  >
                    {isReplyAudioPlaying ? "Stop playback" : "Play latest reply"}
                  </button>
                </div>

                <p className="section-status">
                  {replyAudioStatus ||
                    (speakRepliesOnThisDevice
                      ? "Jarvin will try to play reply audio through this device."
                      : "Reply audio is currently muted on this device.")}
                </p>
              </section>

              <section className="nested-panel">
                <div className="section-copy">
                  <h3>Host listener and devices</h3>
                  <p>These controls affect the Jarvin machine itself, including microphones physically attached to the host PC.</p>
                </div>

                <div className="button-row">
                  <button type="button" className="start-button" onClick={() => onListenerAction("start")} disabled={isListening}>
                    Start host listener
                  </button>
                  <button type="button" className="pause-button" onClick={() => onListenerAction("stop")} disabled={!isListening}>
                    Pause host listener
                  </button>
                  <button type="button" className="danger-button" onClick={() => onListenerAction("shutdown")}>
                    Shutdown host
                  </button>
                </div>

                <label className="field-stack">
                  <span>Host input device</span>
                  <select value={selectedDeviceIndex} onChange={(event) => onSelectAudioDevice(Number(event.currentTarget.value))}>
                    <option value="" disabled>
                      Choose a host input device
                    </option>
                    {(audioDevices?.devices ?? []).map((device) => (
                      <option key={device.index} value={device.index}>
                        [{device.index}] {device.name}
                      </option>
                    ))}
                  </select>
                </label>

                <p className="section-status">
                  {deviceStatus ||
                    (audioDevices?.selected_name
                      ? `Current host input: [${audioDevices.selected_index}] ${audioDevices.selected_name}`
                      : "No host input device selected.")}
                </p>
              </section>
            </section>
          ) : null}

          {activeInspectorSection === "profile" ? (
            <section className="inspector-panel-body">
              <div className="section-copy">
                <h3>Profile and personalization</h3>
                <p>These preferences live on the host so future clients can inherit the same assistant behavior.</p>
              </div>

              <form className="profile-grid" onSubmit={onSaveProfile}>
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
          ) : null}

          {activeInspectorSection === "diagnostics" ? (
            <section className="inspector-panel-body">
              <div className="section-copy">
                <h3>Diagnostics</h3>
                <p>Operational details stay accessible without forcing the whole app to become a dashboard.</p>
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
          ) : null}
        </div>
      </section>
    </div>
  );
}
