import type { FormEvent, KeyboardEvent as ReactKeyboardEvent, MouseEvent, PointerEvent as ReactPointerEvent, RefObject } from "react";
import { ConversationSidebar } from "./ConversationSidebar";
import { ChatWorkspace } from "./ChatWorkspace";
import { SettingsOverlay } from "./SettingsOverlay";
import type {
  AgentActionLogItem,
  AgentAccessMode,
  AudioDevicesResponse,
  ConversationSummary,
  ConversationTurn,
  HealthResponse,
  LLMOptionsResponse,
  LiveSnapshot,
  StatusResponse,
  UserProfilePayload,
} from "../lib/types";
import type { ConnectionState, PendingVoiceReview, RemoteVoiceDiagnostics, SendSource } from "../lib/runtime";
import type { InspectorSection, ReasoningEffort } from "../lib/ui";

type AppWorkspaceShellProps = {
  activeConversationId: number | null;
  activeConversationTitle: string;
  activeInspectorSection: InspectorSection;
  agentAccessMode: AgentAccessMode;
  agentActionLog: AgentActionLogItem[];
  agentActionLogStatus: string;
  apiBaseUrl: string;
  apiBaseUrlDraft: string;
  apiBaseUrlStatus: string;
  audioDevices: AudioDevicesResponse | null;
  chatInput: string;
  chatStatus: string;
  connectionState: ConnectionState;
  connectionSummary: string;
  conversations: ConversationSummary[];
  currentListenerStatus: string;
  deviceStatus: string;
  editingConversationId: number | null;
  editingConversationTitle: string;
  health: HealthResponse | null;
  history: ConversationTurn[];
  isClientOnline: boolean;
  isListening: boolean;
  isMobileSidebarOpen: boolean;
  isRemoteRecording: boolean;
  isRemoteTranscribing: boolean;
  isReplyAudioPlaying: boolean;
  isSettingsOpen: boolean;
  lastConnectionError: string;
  lastNotificationSyncLabel: string;
  lastRoundTripMs: number | null;
  lastSuccessfulContactLabel: string;
  latestReplyAudioReady: boolean;
  llmOptions: LLMOptionsResponse | null;
  llmStatus: string;
  live: LiveSnapshot | null;
  messageListRef: RefObject<HTMLDivElement | null>;
  notificationsEnabled: boolean;
  notificationsSupported: boolean;
  notificationNeedsSystemSettings: boolean;
  notificationPermission: import("../lib/notifications").ReminderNotificationPermission;
  notificationStatus: string;
  notificationSyncing: boolean;
  openConversationMenuId: number | null;
  profile: UserProfilePayload;
  profileStatus: string;
  reasoningEffort: ReasoningEffort;
  remoteRecordingElapsedLabel: string;
  remoteVoiceAvailable: boolean;
  remoteVoiceDiagnostics: RemoteVoiceDiagnostics;
  remoteVoiceDisabledReason: string;
  remoteVoicePressToTalk: boolean;
  remoteVoiceStatus: string;
  pendingVoiceReview: PendingVoiceReview | null;
  replyAudioStatus: string;
  scheduledReminderCount: number;
  selectedBackend: string;
  selectedDeviceIndex: number | "";
  selectedModel: string;
  sending: boolean;
  speakRepliesOnThisDevice: boolean;
  status: StatusResponse | null;
  backendChoices: LLMOptionsResponse["backend_choices"];
  modelChoices: Array<{ value: string; label: string }>;
  onEditingConversationTitleChange: (value: string) => void;
  onApprovePendingAction: () => void;
  onApiBaseUrlDraftChange: (value: string) => void;
  onApplyLlmSettings: () => void;
  onCancelRenameConversation: () => void;
  onTrustPendingAction: () => void;
  onTrustPendingSession: () => void;
  onChatInputChange: (value: string) => void;
  onClearApiBaseUrl: () => void;
  onClearConversation: (conversationId: number) => void;
  onCloseMobileSidebar: () => void;
  onCloseSettings: () => void;
  onComposerKeyDown: (event: ReactKeyboardEvent<HTMLTextAreaElement>) => void;
  onCreateConversation: () => void;
  onDeleteConversation: (conversationId: number) => void;
  onDenyPendingAction: () => void;
  onListenerAction: (action: "start" | "stop" | "shutdown") => void;
  onOpenConversationSidebar: () => void;
  onOpenSettings: () => void;
  onPlayLatestReplyAudio: () => void;
  onDismissVoiceReview: () => void;
  onReconnectHost: () => void;
  onRefreshAgentActionLog: () => void;
  onRefreshLlmSettings: () => void;
  onRefreshWorkspace: () => void;
  onRemoteVoicePressCancel: (event: ReactPointerEvent<HTMLButtonElement>) => void;
  onRemoteVoicePressEnd: (event: ReactPointerEvent<HTMLButtonElement>) => void;
  onRemoteVoicePressStart: (event: ReactPointerEvent<HTMLButtonElement>) => void;
  onRenameConversationSubmit: (event: FormEvent<HTMLFormElement>, conversationId: number) => void;
  onRequestNotificationsPermission: () => void;
  onSaveApiBaseUrl: () => void;
  onSaveProfile: (event: FormEvent<HTMLFormElement>) => void;
  onSectionChange: (section: InspectorSection) => void;
  onSelectAudioDevice: (index: number) => void;
  onSelectConversation: (conversationId: number) => void;
  onSelectedBackendChange: (value: string) => void;
  onSelectedModelChange: (value: string) => void;
  onSendMessage: (rawText?: string, source?: SendSource) => void | Promise<void>;
  onSetNotificationsEnabled: (value: boolean) => void;
  onStartRenameConversation: (event: MouseEvent<HTMLButtonElement>, conversation: ConversationSummary) => void;
  onSyncNotifications: () => void;
  onToggleConversationMenu: (event: MouseEvent<HTMLButtonElement>, conversationId: number) => void;
  onToggleRemoteVoice: () => void;
  onToggleSpeakRepliesOnThisDevice: () => void;
  onReasoningEffortChange: (value: ReasoningEffort) => void;
  onSendTestNotification: () => void;
  onProfileChange: (updater: (current: UserProfilePayload) => UserProfilePayload) => void;
  onAgentAccessModeChange: (value: AgentAccessMode) => void;
  onRetryVoiceReview: () => void;
  onSendHeardVoiceReview: () => void;
  onUseSuggestedVoiceReview: () => void;
};

export function AppWorkspaceShell({
  activeConversationId,
  activeConversationTitle,
  activeInspectorSection,
  agentAccessMode,
  agentActionLog,
  agentActionLogStatus,
  apiBaseUrl,
  apiBaseUrlDraft,
  apiBaseUrlStatus,
  audioDevices,
  backendChoices,
  chatInput,
  chatStatus,
  connectionState,
  connectionSummary,
  conversations,
  currentListenerStatus,
  deviceStatus,
  editingConversationId,
  editingConversationTitle,
  health,
  history,
  isClientOnline,
  isListening,
  isMobileSidebarOpen,
  isRemoteRecording,
  isRemoteTranscribing,
  isReplyAudioPlaying,
  isSettingsOpen,
  lastConnectionError,
  lastNotificationSyncLabel,
  lastRoundTripMs,
  lastSuccessfulContactLabel,
  latestReplyAudioReady,
  llmOptions,
  llmStatus,
  live,
  messageListRef,
  modelChoices,
  notificationNeedsSystemSettings,
  notificationPermission,
  notificationStatus,
  notificationsEnabled,
  notificationsSupported,
  notificationSyncing,
  openConversationMenuId,
  profile,
  profileStatus,
  reasoningEffort,
  remoteRecordingElapsedLabel,
  remoteVoiceAvailable,
  remoteVoiceDiagnostics,
  remoteVoiceDisabledReason,
  remoteVoicePressToTalk,
  remoteVoiceStatus,
  pendingVoiceReview,
  replyAudioStatus,
  scheduledReminderCount,
  selectedBackend,
  selectedDeviceIndex,
  selectedModel,
  sending,
  speakRepliesOnThisDevice,
  status,
  onAgentAccessModeChange,
  onApiBaseUrlDraftChange,
  onApplyLlmSettings,
  onApprovePendingAction,
  onCancelRenameConversation,
  onTrustPendingAction,
  onTrustPendingSession,
  onChatInputChange,
  onClearApiBaseUrl,
  onClearConversation,
  onCloseMobileSidebar,
  onCloseSettings,
  onComposerKeyDown,
  onCreateConversation,
  onDeleteConversation,
  onDenyPendingAction,
  onEditingConversationTitleChange,
  onListenerAction,
  onOpenConversationSidebar,
  onOpenSettings,
  onPlayLatestReplyAudio,
  onDismissVoiceReview,
  onProfileChange,
  onReconnectHost,
  onRefreshAgentActionLog,
  onRefreshLlmSettings,
  onRefreshWorkspace,
  onRemoteVoicePressCancel,
  onRemoteVoicePressEnd,
  onRemoteVoicePressStart,
  onRenameConversationSubmit,
  onRequestNotificationsPermission,
  onSaveApiBaseUrl,
  onSaveProfile,
  onSectionChange,
  onSelectAudioDevice,
  onSelectConversation,
  onSelectedBackendChange,
  onSelectedModelChange,
  onSendMessage,
  onSendTestNotification,
  onSetNotificationsEnabled,
  onStartRenameConversation,
  onSyncNotifications,
  onToggleConversationMenu,
  onToggleRemoteVoice,
  onToggleSpeakRepliesOnThisDevice,
  onReasoningEffortChange,
  onRetryVoiceReview,
  onSendHeardVoiceReview,
  onUseSuggestedVoiceReview,
}: AppWorkspaceShellProps) {
  return (
    <main className={`app-shell ${isMobileSidebarOpen ? "mobile-sidebar-open" : ""}`}>
      {isMobileSidebarOpen ? (
        <button
          type="button"
          className="mobile-sidebar-backdrop"
          aria-label="Close conversations"
          onClick={onCloseMobileSidebar}
        />
      ) : null}

      <section className="workspace-grid">
        <ConversationSidebar
          conversations={conversations}
          activeConversationId={activeConversationId}
          openConversationMenuId={openConversationMenuId}
          editingConversationId={editingConversationId}
          editingConversationTitle={editingConversationTitle}
          onEditingConversationTitleChange={onEditingConversationTitleChange}
          onSelectConversation={onSelectConversation}
          onCreateConversation={onCreateConversation}
          onToggleConversationMenu={onToggleConversationMenu}
          onStartRenameConversation={onStartRenameConversation}
          onCancelRenameConversation={onCancelRenameConversation}
          onRenameConversationSubmit={onRenameConversationSubmit}
          onClearConversation={onClearConversation}
          onDeleteConversation={onDeleteConversation}
          isMobileOpen={isMobileSidebarOpen}
          onCloseMobile={onCloseMobileSidebar}
        />

        <ChatWorkspace
          activeConversationTitle={activeConversationTitle}
          history={history}
          messageListRef={messageListRef}
          chatStatus={chatStatus}
          connectionState={connectionState}
          connectionSummary={connectionSummary}
          lastConnectionError={lastConnectionError}
          replyAudioStatus={replyAudioStatus}
          latestReplyAudioReady={latestReplyAudioReady}
          isReplyAudioPlaying={isReplyAudioPlaying}
          chatInput={chatInput}
          sending={sending}
          currentListenerStatus={currentListenerStatus}
          isListening={Boolean(status?.listening)}
          backendChoices={backendChoices}
          selectedBackend={selectedBackend}
          selectedModel={selectedModel}
          modelChoices={modelChoices}
          reasoningEffort={reasoningEffort}
          onChatInputChange={onChatInputChange}
          onStartListener={() => onListenerAction("start")}
          onPauseListener={() => onListenerAction("stop")}
          onShutdownListener={() => onListenerAction("shutdown")}
          onSelectedBackendChange={onSelectedBackendChange}
          onSelectedModelChange={onSelectedModelChange}
          onReasoningEffortChange={onReasoningEffortChange}
          onComposerKeyDown={onComposerKeyDown}
          onSendMessage={() => onSendMessage()}
          onApprovePendingAction={onApprovePendingAction}
          onDenyPendingAction={onDenyPendingAction}
          onTrustPendingAction={onTrustPendingAction}
          onTrustPendingSession={onTrustPendingSession}
          remoteVoiceAvailable={remoteVoiceAvailable}
          remoteVoiceBusy={isRemoteTranscribing}
          remoteVoiceDisabledReason={remoteVoiceDisabledReason}
          remoteVoiceStatus={remoteVoiceStatus}
          pendingVoiceReview={pendingVoiceReview}
          isRemoteRecording={isRemoteRecording}
          remoteRecordingElapsedLabel={remoteRecordingElapsedLabel}
          remoteVoicePressToTalk={remoteVoicePressToTalk}
          speakRepliesOnThisDevice={speakRepliesOnThisDevice}
          onToggleRemoteVoice={onToggleRemoteVoice}
          onRemoteVoicePressStart={onRemoteVoicePressStart}
          onRemoteVoicePressEnd={onRemoteVoicePressEnd}
          onRemoteVoicePressCancel={onRemoteVoicePressCancel}
          onPlayLatestReplyAudio={onPlayLatestReplyAudio}
          onDismissVoiceReview={onDismissVoiceReview}
          onToggleSpeakRepliesOnThisDevice={onToggleSpeakRepliesOnThisDevice}
          onReconnectHost={onReconnectHost}
          onOpenConversationSidebar={onOpenConversationSidebar}
          onOpenSettings={onOpenSettings}
          onRetryVoiceReview={onRetryVoiceReview}
          onSendHeardVoiceReview={onSendHeardVoiceReview}
          onUseSuggestedVoiceReview={onUseSuggestedVoiceReview}
        />
      </section>

      <SettingsOverlay
        isOpen={isSettingsOpen}
        onClose={onCloseSettings}
        apiBaseUrl={apiBaseUrl}
        apiBaseUrlDraft={apiBaseUrlDraft}
        onApiBaseUrlDraftChange={onApiBaseUrlDraftChange}
        onSaveApiBaseUrl={onSaveApiBaseUrl}
        onClearApiBaseUrl={onClearApiBaseUrl}
        apiBaseUrlStatus={apiBaseUrlStatus}
        currentListenerStatus={currentListenerStatus}
        currentModel={llmOptions?.current_model ?? "Unknown"}
        currentBackend={llmOptions?.current_backend ?? "Unknown"}
        agentAccessMode={agentAccessMode}
        agentActionLog={agentActionLog}
        agentActionLogStatus={agentActionLogStatus}
        onAgentAccessModeChange={onAgentAccessModeChange}
        activeInspectorSection={activeInspectorSection}
        onSectionChange={onSectionChange}
        onRefreshWorkspace={onRefreshWorkspace}
        onReconnectHost={onReconnectHost}
        onRefreshAgentActionLog={onRefreshAgentActionLog}
        llmOptions={llmOptions}
        selectedBackend={selectedBackend}
        selectedModel={selectedModel}
        onSelectedBackendChange={onSelectedBackendChange}
        onSelectedModelChange={onSelectedModelChange}
        onRefreshLlmSettings={onRefreshLlmSettings}
        onApplyLlmSettings={onApplyLlmSettings}
        llmStatus={llmStatus}
        audioDevices={audioDevices}
        selectedDeviceIndex={selectedDeviceIndex}
        onSelectAudioDevice={onSelectAudioDevice}
        onListenerAction={onListenerAction}
        isListening={isListening}
        deviceStatus={deviceStatus}
        remoteVoiceAvailable={remoteVoiceAvailable}
        remoteVoiceDisabledReason={remoteVoiceDisabledReason}
        remoteVoiceStatus={remoteVoiceStatus}
        isRemoteRecording={isRemoteRecording}
        isRemoteTranscribing={isRemoteTranscribing}
        remoteRecordingElapsedLabel={remoteRecordingElapsedLabel}
        remoteVoicePressToTalk={remoteVoicePressToTalk}
        onToggleRemoteVoice={onToggleRemoteVoice}
        speakRepliesOnThisDevice={speakRepliesOnThisDevice}
        onToggleSpeakRepliesOnThisDevice={onToggleSpeakRepliesOnThisDevice}
        replyAudioStatus={replyAudioStatus}
        latestReplyAudioReady={latestReplyAudioReady}
        isReplyAudioPlaying={isReplyAudioPlaying}
        onPlayLatestReplyAudio={onPlayLatestReplyAudio}
        connectionState={connectionState}
        connectionSummary={connectionSummary}
        lastConnectionError={lastConnectionError}
        lastSuccessfulContactLabel={lastSuccessfulContactLabel}
        lastRoundTripMs={lastRoundTripMs}
        isClientOnline={isClientOnline}
        health={health}
        remoteVoiceDiagnostics={remoteVoiceDiagnostics}
        notificationsSupported={notificationsSupported}
        notificationsEnabled={notificationsEnabled}
        notificationPermission={notificationPermission}
        notificationNeedsSystemSettings={notificationNeedsSystemSettings}
        notificationStatus={notificationStatus}
        notificationSyncing={notificationSyncing}
        scheduledReminderCount={scheduledReminderCount}
        lastNotificationSyncLabel={lastNotificationSyncLabel}
        onSetNotificationsEnabled={onSetNotificationsEnabled}
        onRequestNotificationsPermission={onRequestNotificationsPermission}
        onSyncNotifications={onSyncNotifications}
        onSendTestNotification={onSendTestNotification}
        profile={profile}
        onProfileChange={onProfileChange}
        onSaveProfile={onSaveProfile}
        profileStatus={profileStatus}
        live={live}
      />
    </main>
  );
}
