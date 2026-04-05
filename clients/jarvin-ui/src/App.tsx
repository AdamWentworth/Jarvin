import { FormEvent, KeyboardEvent as ReactKeyboardEvent, useEffect, useRef, useState } from "react";
import "./App.css";
import "./App.chat.css";
import "./App.chrome.css";
import "./App.layout.css";
import {
  activateConversation,
  createConversation,
  respondToApproval,
  saveProfile,
  sendChatMessage,
} from "./lib/api";
import type { AgentAccessMode, UserProfilePayload } from "./lib/types";
import {
  DEFAULT_PROFILE,
  historyTitle,
  reasoningToChatMode,
  type InspectorSection,
  type ReasoningEffort,
} from "./lib/ui";
import {
  getStoredAgentAccessMode,
  getStoredChatDraft,
  setStoredAgentAccessMode,
  setStoredChatDraft,
  type SendSource,
} from "./lib/runtime";
import { useReminderNotifications } from "./hooks/useReminderNotifications";
import { useRemoteVoice } from "./hooks/useRemoteVoice";
import { useJarvinHost } from "./hooks/useJarvinHost";
import { useConversationWorkspace } from "./hooks/useConversationWorkspace";
import { AppWorkspaceShell } from "./components/AppWorkspaceShell";
import { describeError } from "./lib/workspace";

function App() {
  const [profile, setProfile] = useState<UserProfilePayload>(DEFAULT_PROFILE);
  const [chatInput, setChatInput] = useState("");
  const [reasoningEffort, setReasoningEffort] = useState<ReasoningEffort>("medium");
  const [agentAccessMode, setAgentAccessMode] = useState<AgentAccessMode>(() => getStoredAgentAccessMode());
  const [chatStatus, setChatStatus] = useState("");
  const [profileStatus, setProfileStatus] = useState("");
  const [activeInspectorSection, setActiveInspectorSection] = useState<InspectorSection>("general");
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const messageListRef = useRef<HTMLDivElement | null>(null);

  const workspace = useConversationWorkspace({
    describeError,
    onProfileSync: setProfile,
    onStatusChange: setChatStatus,
    onChatInputReset: () => setChatInput(""),
    onCloseMobileSidebar: () => setIsMobileSidebarOpen(false),
  });

  const host = useJarvinHost({
    activeConversationId: workspace.activeConversationId,
    describeError,
    onWorkspaceSync: workspace.syncWorkspace,
    reportError: setChatStatus,
    sending,
  });

  async function handleSendMessage(rawText?: string, source: SendSource = "typed") {
    const text = (rawText ?? chatInput).trim();
    if (!text || sending) {
      return;
    }

    if (isReplyAudioPlaying) {
      stopReplyAudio({ quiet: true });
    }

    if (source === "typed") {
      setRemoteVoiceDiagnostics((current) => ({
        ...current,
        chat: "working",
        note: "Sending typed message to the host.",
      }));
    } else {
      setRemoteVoiceDiagnostics((current) => ({
        ...current,
        chat: "working",
        note: "Sending transcribed speech to the host chat endpoint.",
      }));
    }

    let conversationId = workspace.activeConversationId;
    if (conversationId === null) {
      try {
        const createdWorkspace = await createConversation();
        workspace.syncWorkspace(createdWorkspace);
        conversationId = createdWorkspace.active_conversation_id;
      } catch (error) {
        setRemoteVoiceStage("chat", "error");
        setRemoteVoiceDiagnostics((current) => ({ ...current, note: "Could not create a conversation for the new message." }));
        setChatStatus(describeError(error));
        return;
      }
    }

    setSending(true);
    try {
      if (
        host.selectedBackend !== (host.llmOptions?.current_backend ?? "") ||
        host.selectedModel !== (host.llmOptions?.current_model ?? "")
      ) {
        setChatStatus("Switching model...");
        await host.handleApplyLlmSettings();
      }

      setChatStatus("Thinking...");
      const response = await sendChatMessage({
        userText: text,
        conversationId,
        mode: reasoningToChatMode(reasoningEffort),
        speakReply: speakRepliesOnThisDevice,
        agentAccessMode,
      });
      const nextConversationId = response.conversation_id ?? conversationId;
      if (nextConversationId === null) {
        throw new Error("Jarvin did not return a conversation id for this reply.");
      }

      const activatedWorkspace = await activateConversation(nextConversationId);
      workspace.syncWorkspace(activatedWorkspace);
      if (rawText === undefined) {
        setChatInput("");
      }

      if (response.tts_url) {
        setLatestReplyAudioUrl(response.tts_url);
        setRemoteVoiceStage("chat", "done");
        if (speakRepliesOnThisDevice) {
          try {
            await playReplyAudio(response.tts_url);
          } catch {
            setReplyAudioStatus("Reply audio is ready. Tap play to hear it on this device.");
          }
        } else {
          setReplyAudioStatus("Reply audio is ready.");
          setRemoteVoiceStage("playback", "done");
        }
      } else {
        setLatestReplyAudioUrl(null);
        setReplyAudioStatus(speakRepliesOnThisDevice ? "Reply audio was not available for this response." : "");
        setRemoteVoiceStage("chat", "done");
        setRemoteVoiceStage("playback", speakRepliesOnThisDevice ? "error" : "idle");
      }

      setRemoteVoiceDiagnostics((current) => ({
        ...current,
        note: source === "remote_voice" ? "Remote speech completed its round trip." : "Typed message completed successfully.",
      }));
      if (notificationsEnabled) {
        void syncReminderNotifications();
      }
      void host.refreshAgentActionLog();
      setChatStatus("");
    } catch (error) {
      setRemoteVoiceStage("chat", "error");
      setRemoteVoiceDiagnostics((current) => ({ ...current, note: describeError(error) }));
      setChatStatus(describeError(error));
    } finally {
      setSending(false);
    }
  }

  const {
    handlePlayLatestReplyAudio,
    handleRemoteVoicePressCancel,
    handleRemoteVoicePressEnd,
    handleRemoteVoicePressStart,
    handleRemoteVoiceToggle,
    handleToggleSpeakRepliesOnThisDevice,
    isRemoteRecording,
    isRemoteTranscribing,
    isReplyAudioPlaying,
    latestReplyAudioUrl,
    playReplyAudio,
    remoteRecordingElapsedLabel,
    remoteVoiceCapability,
    remoteVoiceDiagnostics,
    remoteVoicePressToTalk,
    remoteVoiceStatus,
    replyAudioStatus,
    setLatestReplyAudioUrl,
    setReplyAudioStatus,
    setRemoteVoiceDiagnostics,
    setRemoteVoiceStage,
    speakRepliesOnThisDevice,
    stopReplyAudio,
  } = useRemoteVoice({
    describeError,
    onSendMessage: async (text, source) => {
      await handleSendMessage(text, source);
    },
  });

  const {
    notificationsEnabled,
    notificationsSupported,
    notificationPermission,
    notificationNeedsSystemSettings,
    notificationStatus,
    notificationSyncing,
    scheduledReminderCount,
    lastNotificationSyncAt,
    requestNotificationsPermission,
    sendTestNotification,
    setNotificationsEnabled,
    syncReminderNotifications,
  } = useReminderNotifications({
    apiBaseUrl: host.apiBaseUrl,
    isClientOnline: host.isClientOnline,
    describeError,
  });

  useEffect(() => {
    setChatInput(getStoredChatDraft(workspace.activeConversationId));
  }, [workspace.activeConversationId]);

  useEffect(() => {
    setStoredChatDraft(workspace.activeConversationId, chatInput);
  }, [workspace.activeConversationId, chatInput]);

  useEffect(() => {
    const node = messageListRef.current;
    if (!node) {
      return;
    }
    node.scrollTop = node.scrollHeight;
  }, [workspace.history, sending]);

  useEffect(() => {
    if (workspace.openConversationMenuId === null && workspace.editingConversationId === null && !isSettingsOpen) {
      return;
    }

    function handleEscape(event: globalThis.KeyboardEvent) {
      if (event.key !== "Escape") {
        return;
      }
      workspace.setOpenConversationMenuId(null);
      workspace.handleCancelRenameConversation();
      setIsSettingsOpen(false);
    }

    function handleWindowClick() {
      workspace.setOpenConversationMenuId(null);
    }

    window.addEventListener("keydown", handleEscape);
    window.addEventListener("click", handleWindowClick);
    return () => {
      window.removeEventListener("keydown", handleEscape);
      window.removeEventListener("click", handleWindowClick);
    };
  }, [isSettingsOpen, workspace]);

  function handleAgentAccessModeChange(value: AgentAccessMode) {
    setAgentAccessMode(value);
    setStoredAgentAccessMode(value);
  }

  async function handleRespondToApproval(decision: string) {
    const conversationId = workspace.activeConversationId;
    if (conversationId === null || sending) {
      return;
    }

    setSending(true);
    setChatStatus("Processing host action approval...");
    try {
      const response = await respondToApproval({ decision, conversationId });
      const nextConversationId = response.conversation_id ?? conversationId;
      const activatedWorkspace = await activateConversation(nextConversationId);
      workspace.syncWorkspace(activatedWorkspace);
      void host.refreshAgentActionLog(nextConversationId);
      setChatStatus("");
    } catch (error) {
      setChatStatus(describeError(error));
    } finally {
      setSending(false);
    }
  }

  async function handleSaveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setProfileStatus("Saving profile...");
    try {
      const next = await saveProfile(profile);
      setProfile(next);
      setProfileStatus("Profile saved.");
    } catch (error) {
      setProfileStatus(describeError(error));
    }
  }

  function handleComposerKeyDown(event: ReactKeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSendMessage();
    }
  }

  const lastNotificationSyncLabel =
    lastNotificationSyncAt === null ? "Never" : new Date(lastNotificationSyncAt).toLocaleString();

  if (host.loading) {
    return (
      <main className="app-shell loading-shell">
        <section className="loading-card">
          <div className="eyebrow">Jarvin Client</div>
          <h1>Preparing Jarvin</h1>
          <p>Connecting this desktop client to the local host machine and loading the workspace.</p>
        </section>
      </main>
    );
  }

  if (host.connectionError) {
    return (
      <main className="app-shell loading-shell">
        <section className="loading-card error-card">
          <div className="eyebrow">Host Unreachable</div>
          <h1>Jarvin is not answering yet</h1>
          <p>The desktop client could not reach the host at <code>{host.apiBaseUrl}</code>.</p>
          <p className="section-status">{host.connectionError}</p>
          <label className="field-stack">
            <span>Host URL</span>
            <input
              value={host.apiBaseUrlDraft}
              onChange={(event) => host.setApiBaseUrlDraft(event.currentTarget.value)}
              placeholder="http://10.0.0.5:8000"
            />
          </label>
          <div className="button-row">
            <button type="button" className="secondary-button" onClick={() => void host.handleSaveApiBaseUrl()}>
              Save host
            </button>
            <button type="button" className="primary-button" onClick={() => void host.refreshWorkspace({ withLoading: true, reason: "reconnect" })}>
              Retry connection
            </button>
            <button type="button" className="ghost-button" onClick={() => void host.handleClearApiBaseUrlOverride()}>
              Reset host
            </button>
          </div>
          {host.apiBaseUrlStatus ? <p className="section-status">{host.apiBaseUrlStatus}</p> : null}
          <p className="section-status">
            Start the host with <code>python server.py</code>, then retry.
          </p>
        </section>
      </main>
    );
  }

  return (
    <AppWorkspaceShell
      activeConversationId={workspace.activeConversationId}
      activeConversationTitle={historyTitle(workspace.conversations, workspace.activeConversationId)}
      activeInspectorSection={activeInspectorSection}
      agentAccessMode={agentAccessMode}
      agentActionLog={host.agentActionLog}
      agentActionLogStatus={host.agentActionLogStatus}
      apiBaseUrl={host.apiBaseUrl}
      apiBaseUrlDraft={host.apiBaseUrlDraft}
      apiBaseUrlStatus={host.apiBaseUrlStatus}
      audioDevices={host.audioDevices}
      backendChoices={host.llmOptions?.backend_choices ?? []}
      chatInput={chatInput}
      chatStatus={chatStatus}
      connectionState={host.connectionState}
      connectionSummary={host.connectionSummary}
      conversations={workspace.conversations}
      currentListenerStatus={host.currentListenerStatus}
      deviceStatus={host.deviceStatus}
      editingConversationId={workspace.editingConversationId}
      editingConversationTitle={workspace.editingConversationTitle}
      health={host.health}
      history={workspace.history}
      isClientOnline={host.isClientOnline}
      isListening={Boolean(host.status?.listening)}
      isMobileSidebarOpen={isMobileSidebarOpen}
      isRemoteRecording={isRemoteRecording}
      isRemoteTranscribing={isRemoteTranscribing}
      isReplyAudioPlaying={isReplyAudioPlaying}
      isSettingsOpen={isSettingsOpen}
      lastConnectionError={host.lastConnectionError}
      lastNotificationSyncLabel={lastNotificationSyncLabel}
      lastRoundTripMs={host.lastRoundTripMs}
      lastSuccessfulContactLabel={host.lastSuccessfulContactLabel}
      latestReplyAudioReady={Boolean(latestReplyAudioUrl)}
      llmOptions={host.llmOptions}
      llmStatus={host.llmStatus}
      live={host.live}
      messageListRef={messageListRef}
      modelChoices={host.modelChoices}
      notificationNeedsSystemSettings={notificationNeedsSystemSettings}
      notificationPermission={notificationPermission}
      notificationStatus={notificationStatus}
      notificationsEnabled={notificationsEnabled}
      notificationsSupported={notificationsSupported}
      notificationSyncing={notificationSyncing}
      openConversationMenuId={workspace.openConversationMenuId}
      profile={profile}
      profileStatus={profileStatus}
      reasoningEffort={reasoningEffort}
      remoteRecordingElapsedLabel={remoteRecordingElapsedLabel}
      remoteVoiceAvailable={remoteVoiceCapability.available}
      remoteVoiceDiagnostics={remoteVoiceDiagnostics}
      remoteVoiceDisabledReason={remoteVoiceCapability.reason}
      remoteVoicePressToTalk={remoteVoicePressToTalk}
      remoteVoiceStatus={remoteVoiceStatus}
      replyAudioStatus={replyAudioStatus}
      scheduledReminderCount={scheduledReminderCount}
      selectedBackend={host.selectedBackend}
      selectedDeviceIndex={host.selectedDeviceIndex}
      selectedModel={host.selectedModel}
      sending={sending}
      speakRepliesOnThisDevice={speakRepliesOnThisDevice}
      status={host.status}
      onAgentAccessModeChange={handleAgentAccessModeChange}
      onApiBaseUrlDraftChange={host.setApiBaseUrlDraft}
      onApplyLlmSettings={() => void host.handleApplyLlmSettings()}
      onApprovePendingAction={() => void handleRespondToApproval("approve")}
      onCancelRenameConversation={workspace.handleCancelRenameConversation}
      onChatInputChange={setChatInput}
      onClearApiBaseUrl={() => void host.handleClearApiBaseUrlOverride()}
      onClearConversation={(conversationId) => void workspace.handleClearConversation(conversationId)}
      onCloseMobileSidebar={() => setIsMobileSidebarOpen(false)}
      onCloseSettings={() => setIsSettingsOpen(false)}
      onComposerKeyDown={handleComposerKeyDown}
      onCreateConversation={() => void workspace.handleCreateConversation()}
      onDeleteConversation={(conversationId) => void workspace.handleDeleteConversation(conversationId)}
      onDenyPendingAction={() => void handleRespondToApproval("deny")}
      onEditingConversationTitleChange={workspace.setEditingConversationTitle}
      onListenerAction={(action) => void host.handleListenerAction(action)}
      onOpenConversationSidebar={() => setIsMobileSidebarOpen(true)}
      onOpenSettings={() => {
        setActiveInspectorSection("general");
        setIsSettingsOpen(true);
      }}
      onPlayLatestReplyAudio={() => void handlePlayLatestReplyAudio()}
      onProfileChange={setProfile}
      onReconnectHost={() => void host.handleReconnectHost()}
      onRefreshLlmSettings={() => void host.handleRefreshLlmSettings()}
      onRefreshAgentActionLog={() => void host.refreshAgentActionLog()}
      onRefreshWorkspace={() => void host.refreshWorkspace({ withLoading: false, reason: "manual" })}
      onRemoteVoicePressCancel={handleRemoteVoicePressCancel}
      onRemoteVoicePressEnd={handleRemoteVoicePressEnd}
      onRemoteVoicePressStart={handleRemoteVoicePressStart}
      onRenameConversationSubmit={(event, conversationId) => void workspace.handleRenameConversationSubmit(event, conversationId)}
      onRequestNotificationsPermission={() => void requestNotificationsPermission()}
      onSaveApiBaseUrl={() => void host.handleSaveApiBaseUrl()}
      onSaveProfile={(event) => void handleSaveProfile(event)}
      onSectionChange={setActiveInspectorSection}
      onSelectAudioDevice={(index) => void host.handleSelectAudioDevice(index)}
      onSelectConversation={(conversationId) => void workspace.handleSelectConversation(conversationId)}
      onSelectedBackendChange={host.handleSelectedBackendChange}
      onSelectedModelChange={host.setSelectedModel}
      onSendMessage={(rawText, source) => void handleSendMessage(rawText, source)}
      onSendTestNotification={() => void sendTestNotification()}
      onSetNotificationsEnabled={(value) => void setNotificationsEnabled(value)}
      onStartRenameConversation={workspace.handleStartRenameConversation}
      onSyncNotifications={() => void syncReminderNotifications()}
      onTrustPendingAction={() => void handleRespondToApproval("trust this chat")}
      onTrustPendingSession={() => void handleRespondToApproval("trust this session")}
      onToggleConversationMenu={workspace.handleToggleConversationMenu}
      onToggleRemoteVoice={() => void handleRemoteVoiceToggle()}
      onToggleSpeakRepliesOnThisDevice={handleToggleSpeakRepliesOnThisDevice}
      onReasoningEffortChange={setReasoningEffort}
    />
  );
}

export default App;
