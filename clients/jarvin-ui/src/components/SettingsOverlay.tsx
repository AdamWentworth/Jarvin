import type { FormEvent, MouseEvent } from "react";
import type { AudioDevicesResponse, LLMOptionsResponse, LiveSnapshot, UserProfilePayload } from "../lib/types";
import {
  COMMUNICATION_STYLE_OPTIONS,
  INSPECTOR_SECTIONS,
  MOOD_OPTIONS,
  RESPONSE_LENGTH_OPTIONS,
  type InspectorSection,
} from "../lib/ui";

type SettingsOverlayProps = {
  isOpen: boolean;
  onClose: () => void;
  apiBaseUrl: string;
  currentListenerStatus: string;
  currentModel: string;
  currentBackend: string;
  activeInspectorSection: InspectorSection;
  onSectionChange: (section: InspectorSection) => void;
  onRefreshWorkspace: () => void;
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
  currentListenerStatus,
  currentModel,
  currentBackend,
  activeInspectorSection,
  onSectionChange,
  onRefreshWorkspace,
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
            <button type="button" className="ghost-button compact-button" onClick={onClose}>
              Close
            </button>
          </div>
        </header>

        <div className="settings-dialog-body">
          <section className="overview-card">
            <div className="overview-grid">
              <div className="overview-stat">
                <span>Host</span>
                <strong>{apiBaseUrl}</strong>
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
                <h3>Voice and devices</h3>
                <p>Host voice controls stay available, but they no longer sit in the main chat column.</p>
              </div>

              <div className="button-row">
                <button type="button" className="start-button" onClick={() => onListenerAction("start")} disabled={isListening}>
                  Start
                </button>
                <button type="button" className="pause-button" onClick={() => onListenerAction("stop")} disabled={!isListening}>
                  Pause
                </button>
                <button type="button" className="danger-button" onClick={() => onListenerAction("shutdown")}>
                  Shutdown
                </button>
              </div>

              <label className="field-stack">
                <span>Input device</span>
                <select value={selectedDeviceIndex} onChange={(event) => onSelectAudioDevice(Number(event.currentTarget.value))}>
                  <option value="" disabled>
                    Choose an input device
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
                    ? `Current input: [${audioDevices.selected_index}] ${audioDevices.selected_name}`
                    : "No input device selected.")}
              </p>
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
          ) : null}
        </div>
      </section>
    </div>
  );
}
