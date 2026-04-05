import type { MouseEvent } from "react";
import { INSPECTOR_SECTIONS } from "../lib/ui";
import {
  SettingsDiagnosticsSection,
  SettingsGeneralSection,
  SettingsNotificationsSection,
  SettingsProfileSection,
  SettingsVoiceSection,
} from "./settings/SettingsSections";
import type { SettingsOverlayProps } from "./settings/SettingsOverlay.types";

export type { SettingsOverlayProps } from "./settings/SettingsOverlay.types";

export function SettingsOverlay(props: SettingsOverlayProps) {
  const {
    activeInspectorSection,
    agentAccessMode,
    apiBaseUrl,
    apiBaseUrlDraft,
    apiBaseUrlStatus,
    connectionSummary,
    currentBackend,
    currentListenerStatus,
    currentModel,
    isOpen,
    agentActionLog,
    agentActionLogStatus,
    notificationPermission,
    notificationsEnabled,
    notificationsSupported,
    onAgentAccessModeChange,
    onApiBaseUrlDraftChange,
    onApplyLlmSettings,
    onClearApiBaseUrl,
    onClose,
    onRefreshAgentActionLog,
    onReconnectHost,
    onRefreshLlmSettings,
    onRefreshWorkspace,
    onSaveApiBaseUrl,
    onSectionChange,
    onSelectedBackendChange,
    onSelectedModelChange,
    scheduledReminderCount,
  } = props;

  if (!isOpen) {
    return null;
  }

  const assistantSummary =
    currentModel && currentModel !== "Unknown" ? `${currentBackend} / ${currentModel}` : currentBackend;
  const accessSummary =
    (
      {
        read_only: "Read only",
        approve_risky: "Approve risky actions",
        full_access: "Trusted host tool access",
      } as const
    )[agentAccessMode] ?? "Approve risky actions";
  const notificationSummary = !notificationsSupported
    ? "Browser only"
    : notificationsEnabled
      ? `${scheduledReminderCount} scheduled`
      : notificationPermission === "granted"
        ? "Ready"
        : "Disabled";

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
          <div className="settings-title-block">
            <div className="eyebrow">Jarvin host</div>
            <h2>Settings</h2>
            <p>Keep the essentials easy to reach. Deeper diagnostics stay separate.</p>
          </div>

          <div className="settings-dialog-actions">
            <button type="button" className="secondary-button compact-button" onClick={onReconnectHost}>
              Reconnect
            </button>
            <button type="button" className="ghost-button compact-button" onClick={onRefreshWorkspace}>
              Refresh
            </button>
            <button type="button" className="ghost-button compact-button" onClick={onClose}>
              Close
            </button>
          </div>
        </header>

        <section className="settings-summary-strip" aria-label="Settings summary">
          <div className="settings-summary-grid">
            <div className="overview-stat summary-stat">
              <span>Host</span>
              <strong>{apiBaseUrl}</strong>
            </div>
            <div className="overview-stat summary-stat">
              <span>Connection</span>
              <strong>{connectionSummary}</strong>
            </div>
            <div className="overview-stat summary-stat">
              <span>Assistant</span>
              <strong>{assistantSummary}</strong>
            </div>
            <div className="overview-stat summary-stat">
              <span>Agent access</span>
              <strong>{accessSummary}</strong>
            </div>
            <div className="overview-stat summary-stat">
              <span>Listener</span>
              <strong>{currentListenerStatus}</strong>
            </div>
            <div className="overview-stat summary-stat">
              <span>Notifications</span>
              <strong>{notificationSummary}</strong>
            </div>
          </div>
        </section>

        <div className="settings-tabs-shell">
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
        </div>

        <div className="settings-dialog-body">
          {activeInspectorSection === "general" ? (
            <SettingsGeneralSection
              agentAccessMode={agentAccessMode}
              apiBaseUrl={apiBaseUrl}
              apiBaseUrlDraft={apiBaseUrlDraft}
              apiBaseUrlStatus={apiBaseUrlStatus}
              currentBackend={currentBackend}
              currentListenerStatus={currentListenerStatus}
              currentModel={currentModel}
              llmOptions={props.llmOptions}
              llmStatus={props.llmStatus}
              onAgentAccessModeChange={onAgentAccessModeChange}
              onApiBaseUrlDraftChange={onApiBaseUrlDraftChange}
              onApplyLlmSettings={onApplyLlmSettings}
              onClearApiBaseUrl={onClearApiBaseUrl}
              onReconnectHost={onReconnectHost}
              onRefreshLlmSettings={onRefreshLlmSettings}
              onSaveApiBaseUrl={onSaveApiBaseUrl}
              onSelectedBackendChange={onSelectedBackendChange}
              onSelectedModelChange={onSelectedModelChange}
              selectedBackend={props.selectedBackend}
              selectedModel={props.selectedModel}
            />
          ) : null}

          {activeInspectorSection === "voice" ? (
            <SettingsVoiceSection
              audioDevices={props.audioDevices}
              deviceStatus={props.deviceStatus}
              isListening={props.isListening}
              isRemoteRecording={props.isRemoteRecording}
              isRemoteTranscribing={props.isRemoteTranscribing}
              isReplyAudioPlaying={props.isReplyAudioPlaying}
              latestReplyAudioReady={props.latestReplyAudioReady}
              onListenerAction={props.onListenerAction}
              onPlayLatestReplyAudio={props.onPlayLatestReplyAudio}
              onSelectAudioDevice={props.onSelectAudioDevice}
              onToggleRemoteVoice={props.onToggleRemoteVoice}
              onToggleSpeakRepliesOnThisDevice={props.onToggleSpeakRepliesOnThisDevice}
              remoteRecordingElapsedLabel={props.remoteRecordingElapsedLabel}
              remoteVoiceAvailable={props.remoteVoiceAvailable}
              remoteVoiceDisabledReason={props.remoteVoiceDisabledReason}
              remoteVoicePressToTalk={props.remoteVoicePressToTalk}
              remoteVoiceStatus={props.remoteVoiceStatus}
              replyAudioStatus={props.replyAudioStatus}
              selectedDeviceIndex={props.selectedDeviceIndex}
              speakRepliesOnThisDevice={props.speakRepliesOnThisDevice}
            />
          ) : null}

          {activeInspectorSection === "notifications" ? (
            <SettingsNotificationsSection
              lastNotificationSyncLabel={props.lastNotificationSyncLabel}
              notificationNeedsSystemSettings={props.notificationNeedsSystemSettings}
              notificationPermission={props.notificationPermission}
              notificationStatus={props.notificationStatus}
              notificationSyncing={props.notificationSyncing}
              notificationsEnabled={props.notificationsEnabled}
              notificationsSupported={props.notificationsSupported}
              onRequestNotificationsPermission={props.onRequestNotificationsPermission}
              onSendTestNotification={props.onSendTestNotification}
              onSetNotificationsEnabled={props.onSetNotificationsEnabled}
              onSyncNotifications={props.onSyncNotifications}
              scheduledReminderCount={props.scheduledReminderCount}
            />
          ) : null}

          {activeInspectorSection === "profile" ? (
            <SettingsProfileSection
              onProfileChange={props.onProfileChange}
              onSaveProfile={props.onSaveProfile}
              profile={props.profile}
              profileStatus={props.profileStatus}
            />
          ) : null}

          {activeInspectorSection === "diagnostics" ? (
            <SettingsDiagnosticsSection
              agentActionLog={agentActionLog}
              agentActionLogStatus={agentActionLogStatus}
              connectionState={props.connectionState}
              connectionSummary={props.connectionSummary}
              currentListenerStatus={props.currentListenerStatus}
              health={props.health}
              isClientOnline={props.isClientOnline}
              lastConnectionError={props.lastConnectionError}
              lastRoundTripMs={props.lastRoundTripMs}
              lastSuccessfulContactLabel={props.lastSuccessfulContactLabel}
              live={props.live}
              onRefreshAgentActionLog={onRefreshAgentActionLog}
              remoteVoiceDiagnostics={props.remoteVoiceDiagnostics}
            />
          ) : null}
        </div>
      </section>
    </div>
  );
}
