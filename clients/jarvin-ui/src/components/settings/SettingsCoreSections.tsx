import type { AgentAccessMode } from "../../lib/types";
import {
  AGENT_ACCESS_OPTIONS,
} from "../../lib/ui";
import type { ReminderNotificationPermission } from "../../lib/notifications";
import type { SettingsOverlayProps } from "./SettingsOverlay.types";

type GeneralSectionProps = Pick<
  SettingsOverlayProps,
  | "agentAccessMode"
  | "apiBaseUrl"
  | "apiBaseUrlDraft"
  | "apiBaseUrlStatus"
  | "currentBackend"
  | "currentListenerStatus"
  | "currentModel"
  | "llmOptions"
  | "llmStatus"
  | "onAgentAccessModeChange"
  | "onApiBaseUrlDraftChange"
  | "onApplyLlmSettings"
  | "onClearApiBaseUrl"
  | "onReconnectHost"
  | "onRefreshLlmSettings"
  | "onSaveApiBaseUrl"
  | "onSelectedBackendChange"
  | "onSelectedModelChange"
  | "selectedBackend"
  | "selectedModel"
>;

type VoiceSectionProps = Pick<
  SettingsOverlayProps,
  | "audioDevices"
  | "deviceStatus"
  | "isListening"
  | "isRemoteRecording"
  | "isRemoteTranscribing"
  | "isReplyAudioPlaying"
  | "latestReplyAudioReady"
  | "onListenerAction"
  | "onPlayLatestReplyAudio"
  | "onSelectAudioDevice"
  | "onToggleRemoteVoice"
  | "onToggleSpeakRepliesOnThisDevice"
  | "remoteRecordingElapsedLabel"
  | "remoteVoiceAvailable"
  | "remoteVoiceDisabledReason"
  | "remoteVoicePressToTalk"
  | "remoteVoiceStatus"
  | "replyAudioStatus"
  | "selectedDeviceIndex"
  | "speakRepliesOnThisDevice"
>;

type NotificationsSectionProps = Pick<
  SettingsOverlayProps,
  | "lastNotificationSyncLabel"
  | "notificationNeedsSystemSettings"
  | "notificationPermission"
  | "notificationStatus"
  | "notificationSyncing"
  | "notificationsEnabled"
  | "notificationsSupported"
  | "onRequestNotificationsPermission"
  | "onSendTestNotification"
  | "onSetNotificationsEnabled"
  | "onSyncNotifications"
  | "scheduledReminderCount"
>;

function notificationPermissionLabel(permission: ReminderNotificationPermission): string {
  if (permission === "unsupported") {
    return "Unsupported";
  }
  if (permission === "granted") {
    return "Granted";
  }
  if (permission === "denied") {
    return "Denied";
  }
  if (permission === "prompt-with-rationale") {
    return "Needs rationale";
  }
  if (permission === "blocked-in-settings") {
    return "Blocked in settings";
  }
  return "Not requested";
}

export function SettingsGeneralSection({
  agentAccessMode,
  apiBaseUrl,
  apiBaseUrlDraft,
  apiBaseUrlStatus,
  currentBackend,
  currentListenerStatus,
  currentModel,
  llmOptions,
  llmStatus,
  onAgentAccessModeChange,
  onApiBaseUrlDraftChange,
  onApplyLlmSettings,
  onClearApiBaseUrl,
  onReconnectHost,
  onRefreshLlmSettings,
  onSaveApiBaseUrl,
  onSelectedBackendChange,
  onSelectedModelChange,
  selectedBackend,
  selectedModel,
}: GeneralSectionProps) {
  const modelChoices =
    selectedBackend === "ollama_http" ? llmOptions?.ollama_model_choices ?? [] : llmOptions?.local_model_choices ?? [];

  return (
    <section className="inspector-panel-body">
      <section className="nested-panel">
        <div className="section-copy">
          <h3>Agent access</h3>
          <p>Choose how much host power this client can grant Jarvin before it asks for approval, trust, or execution.</p>
        </div>

        <label className="field-stack">
          <span>Access level</span>
          <select value={agentAccessMode} onChange={(event) => onAgentAccessModeChange(event.currentTarget.value as AgentAccessMode)}>
            {AGENT_ACCESS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <p className="section-status">
          {AGENT_ACCESS_OPTIONS.find((item) => item.value === agentAccessMode)?.hint ??
            "Jarvin will use the selected approval model for host actions on this client."}
        </p>
      </section>

      <section className="nested-panel">
        <div className="section-copy">
          <h3>Connection</h3>
          <p>Point this client at the right Jarvin host and keep the link healthy.</p>
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
          <button type="button" className="ghost-button" onClick={onReconnectHost}>
            Reconnect now
          </button>
        </div>

        <p className="section-status">{apiBaseUrlStatus || `Current client target: ${apiBaseUrl}`}</p>
      </section>

      <section className="nested-panel">
        <div className="section-copy">
          <h3>Assistant runtime</h3>
          <p>Backend and model selection stay together here instead of being scattered around the app.</p>
        </div>

        <div className="settings-split-grid">
          <label className="field-stack">
            <span>Backend</span>
            <select value={selectedBackend} onChange={(event) => onSelectedBackendChange(event.currentTarget.value)}>
              {(llmOptions?.backend_choices ?? []).map((choice) => (
                <option key={choice.value} value={choice.value}>
                  {choice.label}
                </option>
              ))}
            </select>
          </label>

          <label className="field-stack">
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
        <p className="section-status">Current listener state: {currentListenerStatus} on {currentBackend} / {currentModel}</p>
      </section>
    </section>
  );
}

export function SettingsVoiceSection({
  audioDevices,
  deviceStatus,
  isListening,
  isRemoteRecording,
  isRemoteTranscribing,
  isReplyAudioPlaying,
  latestReplyAudioReady,
  onListenerAction,
  onPlayLatestReplyAudio,
  onSelectAudioDevice,
  onToggleRemoteVoice,
  onToggleSpeakRepliesOnThisDevice,
  remoteRecordingElapsedLabel,
  remoteVoiceAvailable,
  remoteVoiceDisabledReason,
  remoteVoicePressToTalk,
  remoteVoiceStatus,
  replyAudioStatus,
  selectedDeviceIndex,
  speakRepliesOnThisDevice,
}: VoiceSectionProps) {
  return (
    <section className="inspector-panel-body">
      <div className="section-copy">
        <h3>Voice modes</h3>
        <p>This device audio and host-room audio stay separate so the controls are less confusing.</p>
      </div>

      <section className="nested-panel">
        <div className="section-copy">
          <h3>This device</h3>
          <p>Use your phone or current client for mic input and reply playback.</p>
        </div>

        <div className="settings-split-grid">
          <section className="nested-panel nested-subpanel">
            <div className="section-copy">
              <h3>Microphone</h3>
              <p>{remoteVoicePressToTalk ? "Hold to talk and release to send." : "Use this device microphone for push-to-talk."}</p>
            </div>

            <div className="button-row">
              <button
                type="button"
                className={isRemoteRecording ? "danger-button" : "primary-button"}
                onClick={onToggleRemoteVoice}
                disabled={!remoteVoiceAvailable || isRemoteTranscribing}
                title={remoteVoiceAvailable ? "Use this device microphone" : remoteVoiceDisabledReason}
              >
                {isRemoteTranscribing
                  ? "Transcribing..."
                  : isRemoteRecording
                    ? `Recording ${remoteRecordingElapsedLabel}`
                    : remoteVoicePressToTalk
                      ? "Hold to talk"
                      : "Record from this device"}
              </button>
            </div>

            <p className="section-status">
              {remoteVoiceStatus ||
                (remoteVoiceAvailable ? "Ready to capture audio from this device." : remoteVoiceDisabledReason)}
            </p>
          </section>

          <section className="nested-panel nested-subpanel">
            <div className="section-copy">
              <h3>Reply audio</h3>
              <p>Play Jarvin's spoken replies through this device.</p>
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
                  : "Reply audio is muted on this device.")}
            </p>
          </section>
        </div>
      </section>

      <section className="nested-panel">
        <div className="section-copy">
          <h3>Host machine</h3>
          <p>These controls affect microphones and listener behavior on the Jarvin PC itself.</p>
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
  );
}

export function SettingsNotificationsSection({
  lastNotificationSyncLabel,
  notificationNeedsSystemSettings,
  notificationPermission,
  notificationStatus,
  notificationSyncing,
  notificationsEnabled,
  notificationsSupported,
  onRequestNotificationsPermission,
  onSendTestNotification,
  onSetNotificationsEnabled,
  onSyncNotifications,
  scheduledReminderCount,
}: NotificationsSectionProps) {
  return (
    <section className="inspector-panel-body">
      <div className="section-copy">
        <h3>Phone notifications</h3>
        <p>Use native Android notifications for reminders and brief-style nudges.</p>
      </div>

      <section className="nested-panel">
        <div className="section-copy">
          <h3>Reminder notifications</h3>
          <p>Permission and sync controls come first. Status lives underneath.</p>
        </div>

        <div className="button-row settings-primary-actions">
          <button
            type="button"
            className="secondary-button"
            onClick={onRequestNotificationsPermission}
            disabled={!notificationsSupported}
          >
            {notificationNeedsSystemSettings ? "Check Android settings" : "Allow notifications"}
          </button>
          <button
            type="button"
            className={notificationsEnabled ? "primary-button" : "ghost-button"}
            onClick={() => onSetNotificationsEnabled(!notificationsEnabled)}
            disabled={!notificationsSupported}
          >
            {notificationsEnabled ? "Disable reminder notifications" : "Enable reminder notifications"}
          </button>
          <button
            type="button"
            className="ghost-button"
            onClick={onSyncNotifications}
            disabled={!notificationsSupported || notificationSyncing}
          >
            {notificationSyncing ? "Syncing..." : "Sync reminder notifications"}
          </button>
          <button
            type="button"
            className="ghost-button"
            onClick={onSendTestNotification}
            disabled={!notificationsSupported}
          >
            Send test notification
          </button>
        </div>

        <div className="overview-grid diagnostic-grid">
          <div className="overview-stat">
            <span>Support</span>
            <strong>{notificationsSupported ? "Installed Tauri app" : "Browser client only"}</strong>
          </div>
          <div className="overview-stat">
            <span>Permission</span>
            <strong>{notificationPermissionLabel(notificationPermission)}</strong>
          </div>
          <div className="overview-stat">
            <span>Reminder sync</span>
            <strong>{notificationsEnabled ? "Enabled" : "Disabled"}</strong>
          </div>
          <div className="overview-stat">
            <span>Scheduled reminders</span>
            <strong>{scheduledReminderCount}</strong>
          </div>
          <div className="overview-stat">
            <span>Last sync</span>
            <strong>{lastNotificationSyncLabel}</strong>
          </div>
        </div>

        <p className="section-status">
          {notificationStatus ||
            (notificationsSupported
              ? "Reminder notifications can be scheduled locally on this device once permission is granted."
              : "System notifications require the installed Jarvin Tauri app on this device.")}
        </p>
      </section>
    </section>
  );
}
