import { FormEvent, KeyboardEvent as ReactKeyboardEvent, MouseEvent, useEffect, useMemo, useRef, useState } from "react";
import "./App.css";
import "./App.chrome.css";
import {
  activateConversation,
  applyLlmSelection,
  clearStoredApiBaseUrl,
  clearConversation,
  createConversation,
  deleteConversation,
  getApiBaseUrl,
  getAudioDevices,
  getHealth,
  getLive,
  getLlmOptions,
  getStoredApiBaseUrl,
  getStatus,
  getWorkspaceBootstrap,
  renameConversation,
  saveProfile,
  selectAudioDevice,
  sendChatMessage,
  setStoredApiBaseUrl,
  shutdownHost,
  startListener,
  stopListener,
} from "./lib/api";
import type {
  AudioDevicesResponse,
  ConversationSummary,
  ConversationTurn,
  HealthResponse,
  LLMOptionsResponse,
  LiveSnapshot,
  StatusResponse,
  UserProfilePayload,
} from "./lib/types";
import {
  DEFAULT_PROFILE,
  historyTitle,
  reasoningToChatMode,
  statusLabel,
  type InspectorSection,
  type ReasoningEffort,
} from "./lib/ui";
import {
  connectionLabel,
  formatTimestamp,
  getStoredChatDraft,
  setStoredChatDraft,
  type ConnectionState,
  type SendSource,
} from "./lib/runtime";
import { useReminderNotifications } from "./hooks/useReminderNotifications";
import { useRemoteVoice } from "./hooks/useRemoteVoice";
import { ConversationSidebar } from "./components/ConversationSidebar";
import { ChatWorkspace } from "./components/ChatWorkspace";
import { SettingsOverlay } from "./components/SettingsOverlay";
import { describeError, syncWorkspaceState } from "./lib/workspace";

function App() {
  const apiBaseUrl = getApiBaseUrl();
  const [profile, setProfile] = useState<UserProfilePayload>(DEFAULT_PROFILE);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);
  const [history, setHistory] = useState<ConversationTurn[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [reasoningEffort, setReasoningEffort] = useState<ReasoningEffort>("medium");
  const [llmOptions, setLlmOptions] = useState<LLMOptionsResponse | null>(null);
  const [selectedBackend, setSelectedBackend] = useState("llama_cpp");
  const [selectedModel, setSelectedModel] = useState("");
  const [audioDevices, setAudioDevices] = useState<AudioDevicesResponse | null>(null);
  const [selectedDeviceIndex, setSelectedDeviceIndex] = useState<number | "">("");
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [live, setLive] = useState<LiveSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [isClientOnline, setIsClientOnline] = useState<boolean>(() => (typeof navigator === "undefined" ? true : navigator.onLine));
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");
  const [lastConnectionError, setLastConnectionError] = useState("");
  const [lastSuccessfulContactAt, setLastSuccessfulContactAt] = useState<string | null>(null);
  const [lastRoundTripMs, setLastRoundTripMs] = useState<number | null>(null);
  const [connectionError, setConnectionError] = useState("");
  const [apiBaseUrlDraft, setApiBaseUrlDraft] = useState<string>(() => getStoredApiBaseUrl() ?? getApiBaseUrl());
  const [apiBaseUrlStatus, setApiBaseUrlStatus] = useState("");
  const [chatStatus, setChatStatus] = useState("");
  const [llmStatus, setLlmStatus] = useState("");
  const [profileStatus, setProfileStatus] = useState("");
  const [deviceStatus, setDeviceStatus] = useState("");
  const [openConversationMenuId, setOpenConversationMenuId] = useState<number | null>(null);
  const [editingConversationId, setEditingConversationId] = useState<number | null>(null);
  const [editingConversationTitle, setEditingConversationTitle] = useState("");
  const [activeInspectorSection, setActiveInspectorSection] = useState<InspectorSection>("assistant");
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const lastLiveSeq = useRef<number | null>(null);
  const consecutivePollFailuresRef = useRef(0);
  const messageListRef = useRef<HTMLDivElement | null>(null);
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
    notificationStatus,
    notificationSyncing,
    scheduledReminderCount,
    lastNotificationSyncAt,
    requestNotificationsPermission,
    sendTestNotification,
    setNotificationsEnabled,
    syncReminderNotifications,
  } = useReminderNotifications({
    apiBaseUrl,
    isClientOnline,
    describeError,
  });

  const currentListenerStatus = useMemo(
    () => statusLabel(status, live),
    [status, live],
  );

  const connectionSummary = useMemo(() => {
    if (!isClientOnline) {
      return "Client device is offline";
    }
    const base = connectionLabel(connectionState);
    if (connectionState === "connected") {
      if (lastRoundTripMs !== null) {
        return `${base} • ${lastRoundTripMs} ms`;
      }
      return base;
    }
    if (lastConnectionError) {
      return `${base} • ${lastConnectionError}`;
    }
    return base;
  }, [connectionState, isClientOnline, lastConnectionError, lastRoundTripMs]);

  const lastSuccessfulContactLabel = useMemo(
    () => formatTimestamp(lastSuccessfulContactAt),
    [lastSuccessfulContactAt],
  );
  const lastNotificationSyncLabel = useMemo(
    () => formatTimestamp(lastNotificationSyncAt),
    [lastNotificationSyncAt],
  );

  const chatMode = useMemo(
    () => reasoningToChatMode(reasoningEffort),
    [reasoningEffort],
  );

  const modelChoices = useMemo(() => {
    if (!llmOptions) {
      return [];
    }
    if (selectedBackend === "ollama_http") {
      return llmOptions.ollama_model_choices;
    }
    return llmOptions.local_model_choices;
  }, [llmOptions, selectedBackend]);

  async function refreshConversationWorkspace() {
    const workspace = await getWorkspaceBootstrap();
    syncWorkspaceState(setConversations, setActiveConversationId, setHistory, workspace);
    setProfile(workspace.profile);
  }

  async function refreshWorkspace(options?: { withLoading?: boolean; reason?: "initial" | "manual" | "reconnect" }) {
    const withLoading = options?.withLoading ?? true;
    const startedAt = typeof performance !== "undefined" ? performance.now() : Date.now();
    if (withLoading) {
      setLoading(true);
    }
    setConnectionState(options?.reason === "reconnect" ? "degraded" : "connecting");
    setConnectionError("");
    try {
      const [workspace, llm, devices, currentHealth, currentStatus, currentLive] = await Promise.all([
        getWorkspaceBootstrap(),
        getLlmOptions(),
        getAudioDevices(),
        getHealth(),
        getStatus(),
        getLive(),
      ]);

      syncWorkspaceState(setConversations, setActiveConversationId, setHistory, workspace);
      setProfile(workspace.profile);
      setLlmOptions(llm);
      setSelectedBackend(llm.current_backend);
      setSelectedModel(llm.current_model);
      setLlmStatus(llm.message ?? "");
      setAudioDevices(devices);
      setSelectedDeviceIndex(devices.selected_index ?? "");
      setHealth(currentHealth);
      setStatus(currentStatus);
      setLive(currentLive);
      lastLiveSeq.current = currentLive.seq ?? null;
      setChatStatus("");
      setApiBaseUrlStatus("");
      setConnectionState("connected");
      setLastConnectionError("");
      setLastSuccessfulContactAt(new Date().toISOString());
      setLastRoundTripMs(Math.max(1, Math.round((typeof performance !== "undefined" ? performance.now() : Date.now()) - startedAt)));
      consecutivePollFailuresRef.current = 0;
    } catch (error) {
      const message = describeError(error);
      setConnectionError(message);
      setLastConnectionError(message);
      setConnectionState("offline");
    } finally {
      if (withLoading) {
        setLoading(false);
      }
    }
  }

  useEffect(() => {
    void refreshWorkspace({ withLoading: true, reason: "initial" });
  }, []);

  useEffect(() => {
    if (!llmOptions) {
      return;
    }
    const available = modelChoices.map((item) => item.value);
    if (!available.includes(selectedModel)) {
      setSelectedModel(available[0] ?? "");
    }
  }, [llmOptions, modelChoices, selectedModel]);

  useEffect(() => {
    setChatInput(getStoredChatDraft(activeConversationId));
  }, [activeConversationId]);

  useEffect(() => {
    setStoredChatDraft(activeConversationId, chatInput);
  }, [activeConversationId, chatInput]);

  useEffect(() => {
    function handleOnline() {
      setIsClientOnline(true);
    }

    function handleOffline() {
      setIsClientOnline(false);
    }

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  useEffect(() => {
    const node = messageListRef.current;
    if (!node) {
      return;
    }
    node.scrollTop = node.scrollHeight;
  }, [history, sending]);

  useEffect(() => {
    if (editingConversationId === null) {
      return;
    }
    const match = conversations.find((item) => item.id === editingConversationId);
    if (!match) {
      setEditingConversationId(null);
      setEditingConversationTitle("");
    }
  }, [conversations, editingConversationId]);

  useEffect(() => {
    if (openConversationMenuId === null && editingConversationId === null && !isSettingsOpen) {
      return;
    }

    function handleEscape(event: globalThis.KeyboardEvent) {
      if (event.key !== "Escape") {
        return;
      }
      setOpenConversationMenuId(null);
      setEditingConversationId(null);
      setEditingConversationTitle("");
      setIsSettingsOpen(false);
    }

    function handleWindowClick() {
      setOpenConversationMenuId(null);
    }

    window.addEventListener("keydown", handleEscape);
    window.addEventListener("click", handleWindowClick);
    return () => {
      window.removeEventListener("keydown", handleEscape);
      window.removeEventListener("click", handleWindowClick);
    };
  }, [openConversationMenuId, editingConversationId, isSettingsOpen]);

  useEffect(() => {
    const poll = window.setInterval(async () => {
      try {
        const startedAt = typeof performance !== "undefined" ? performance.now() : Date.now();
        const [currentHealth, currentStatus, currentLive] = await Promise.all([getHealth(), getStatus(), getLive()]);
        setHealth(currentHealth);
        setStatus(currentStatus);
        setLive(currentLive);
        setConnectionState("connected");
        setLastConnectionError("");
        setLastSuccessfulContactAt(new Date().toISOString());
        setLastRoundTripMs(Math.max(1, Math.round((typeof performance !== "undefined" ? performance.now() : Date.now()) - startedAt)));
        consecutivePollFailuresRef.current = 0;

        const nextSeq = currentLive.seq ?? null;
        if (
          nextSeq !== null &&
          nextSeq !== lastLiveSeq.current &&
          activeConversationId !== null &&
          !sending
        ) {
          lastLiveSeq.current = nextSeq;
          const workspace = await activateConversation(activeConversationId);
          syncWorkspaceState(setConversations, setActiveConversationId, setHistory, workspace);
        } else {
          lastLiveSeq.current = nextSeq;
        }
      } catch (error) {
        consecutivePollFailuresRef.current += 1;
        setLastConnectionError(describeError(error));
        setConnectionState(consecutivePollFailuresRef.current >= 3 ? "offline" : "degraded");
      }
    }, 1000);

    return () => window.clearInterval(poll);
  }, [activeConversationId, sending]);

  async function handleReconnectHost() {
    setApiBaseUrlStatus("Reconnecting to the Jarvin host...");
    await refreshWorkspace({ withLoading: false, reason: "reconnect" });
  }

  async function handleSelectConversation(conversationId: number) {
    setOpenConversationMenuId(null);
    setEditingConversationId(null);
    setChatStatus("Loading conversation...");
    try {
      const workspace = await activateConversation(conversationId);
      syncWorkspaceState(setConversations, setActiveConversationId, setHistory, workspace);
      setIsMobileSidebarOpen(false);
      setChatStatus("Conversation ready.");
    } catch (error) {
      setChatStatus(describeError(error));
    }
  }

  async function handleCreateConversation() {
    setOpenConversationMenuId(null);
    setEditingConversationId(null);
    setEditingConversationTitle("");
    setChatStatus("Creating a fresh workspace...");
    try {
      const workspace = await createConversation();
      syncWorkspaceState(setConversations, setActiveConversationId, setHistory, workspace);
      setChatInput("");
      setIsMobileSidebarOpen(false);
      setChatStatus("Fresh chat ready.");
    } catch (error) {
      setChatStatus(describeError(error));
    }
  }

  function handleToggleConversationMenu(event: MouseEvent<HTMLButtonElement>, conversationId: number) {
    event.stopPropagation();
    setEditingConversationId(null);
    setEditingConversationTitle("");
    setOpenConversationMenuId((current) => (current === conversationId ? null : conversationId));
  }

  function handleStartRenameConversation(
    event: MouseEvent<HTMLButtonElement>,
    conversation: ConversationSummary,
  ) {
    event.stopPropagation();
    setOpenConversationMenuId(null);
    setEditingConversationId(conversation.id);
    setEditingConversationTitle(conversation.title);
  }

  function handleCancelRenameConversation() {
    setEditingConversationId(null);
    setEditingConversationTitle("");
  }

  async function handleRenameConversationSubmit(event: FormEvent<HTMLFormElement>, conversationId: number) {
    event.preventDefault();
    const nextTitle = editingConversationTitle.trim();
    if (!nextTitle) {
      setChatStatus("Give the conversation a title first.");
      return;
    }
    try {
      await renameConversation(conversationId, nextTitle);
      await refreshConversationWorkspace();
      setEditingConversationId(null);
      setEditingConversationTitle("");
      setChatStatus("Conversation renamed.");
    } catch (error) {
      setChatStatus(describeError(error));
    }
  }

  async function handleClearConversation(conversationId: number) {
    setOpenConversationMenuId(null);
    if (!window.confirm("Clear this conversation history?")) {
      return;
    }
    try {
      await clearConversation(conversationId);
      await refreshConversationWorkspace();
      setChatStatus("Conversation history cleared.");
    } catch (error) {
      setChatStatus(describeError(error));
    }
  }

  async function handleDeleteConversation(conversationId: number) {
    setOpenConversationMenuId(null);
    if (!window.confirm("Delete this conversation?")) {
      return;
    }
    try {
      await deleteConversation(conversationId);
      await refreshConversationWorkspace();
      setChatStatus("Conversation deleted.");
    } catch (error) {
      setChatStatus(describeError(error));
    }
  }

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

    let conversationId = activeConversationId;
    if (conversationId === null) {
      try {
        const workspace = await createConversation();
        syncWorkspaceState(setConversations, setActiveConversationId, setHistory, workspace);
        conversationId = workspace.active_conversation_id;
      } catch (error) {
        setRemoteVoiceStage("chat", "error");
        setRemoteVoiceDiagnostics((current) => ({ ...current, note: "Could not create a conversation for the new message." }));
        setChatStatus(describeError(error));
        return;
      }
    }

    setSending(true);
    try {
      if (selectedBackend !== (llmOptions?.current_backend ?? "") || selectedModel !== (llmOptions?.current_model ?? "")) {
        setChatStatus("Switching model...");
        const next = await applyLlmSelection(selectedBackend, selectedModel);
        setLlmOptions(next);
        setSelectedBackend(next.current_backend);
        setSelectedModel(next.current_model);
        setLlmStatus(next.message ?? "LLM settings updated.");
      }

      setChatStatus("Thinking...");
      const response = await sendChatMessage({
        userText: text,
        conversationId,
        mode: chatMode,
        speakReply: speakRepliesOnThisDevice,
      });
      const nextConversationId = response.conversation_id ?? conversationId;
      if (nextConversationId === null) {
        throw new Error("Jarvin did not return a conversation id for this reply.");
      }
      const workspace = await activateConversation(nextConversationId);
      syncWorkspaceState(setConversations, setActiveConversationId, setHistory, workspace);
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
      setChatStatus("");
    } catch (error) {
      setRemoteVoiceStage("chat", "error");
      setRemoteVoiceDiagnostics((current) => ({ ...current, note: describeError(error) }));
      setChatStatus(describeError(error));
    } finally {
      setSending(false);
    }
  }

  async function handleApplyLlmSettings() {
    if (!selectedBackend || !selectedModel) {
      setLlmStatus("Choose a backend and model first.");
      return;
    }
    setLlmStatus("Applying LLM settings...");
    try {
      const next = await applyLlmSelection(selectedBackend, selectedModel);
      setLlmOptions(next);
      setSelectedBackend(next.current_backend);
      setSelectedModel(next.current_model);
      setLlmStatus(next.message ?? "LLM settings updated.");
    } catch (error) {
      setLlmStatus(describeError(error));
    }
  }

  async function handleRefreshLlmSettings() {
    try {
      const next = await getLlmOptions();
      setLlmOptions(next);
      setSelectedBackend(next.current_backend);
      setSelectedModel(next.current_model);
      setLlmStatus(next.message ?? "Model list refreshed.");
    } catch (error) {
      setLlmStatus(describeError(error));
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

  async function handleSelectAudioDevice(index: number) {
    setSelectedDeviceIndex(index);
    setDeviceStatus("Applying input device...");
    try {
      const result = await selectAudioDevice(index);
      const devices = await getAudioDevices();
      setAudioDevices(devices);
      setSelectedDeviceIndex(devices.selected_index ?? "");
      setDeviceStatus(result.message ?? "Input device updated.");
    } catch (error) {
      setDeviceStatus(describeError(error));
    }
  }

  async function handleListenerAction(action: "start" | "stop" | "shutdown") {
    try {
      if (action === "start") {
        await startListener();
      } else if (action === "stop") {
        await stopListener();
      } else {
        await shutdownHost();
      }
      const nextStatus = await getStatus();
      setStatus(nextStatus);
    } catch (error) {
      setChatStatus(describeError(error));
    }
  }

  async function handleSaveApiBaseUrl() {
    try {
      const next = setStoredApiBaseUrl(apiBaseUrlDraft);
      setApiBaseUrlDraft(next);
      setApiBaseUrlStatus("Saved host URL. Trying connection...");
      await refreshWorkspace({ withLoading: false, reason: "reconnect" });
    } catch (error) {
      setApiBaseUrlStatus(describeError(error));
    }
  }

  async function handleClearApiBaseUrlOverride() {
    clearStoredApiBaseUrl();
    const next = getApiBaseUrl();
    setApiBaseUrlDraft(next);
    setApiBaseUrlStatus("Using the default host URL again.");
    await refreshWorkspace({ withLoading: false, reason: "reconnect" });
  }

  function handleComposerKeyDown(event: ReactKeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSendMessage();
    }
  }

  function handleSelectedBackendChange(value: string) {
    setSelectedBackend(value);
    const nextChoices = value === "ollama_http" ? llmOptions?.ollama_model_choices ?? [] : llmOptions?.local_model_choices ?? [];
    setSelectedModel(nextChoices[0]?.value ?? "");
  }

  if (loading) {
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

  if (connectionError) {
    return (
      <main className="app-shell loading-shell">
        <section className="loading-card error-card">
          <div className="eyebrow">Host Unreachable</div>
          <h1>Jarvin is not answering yet</h1>
          <p>The desktop client could not reach the host at <code>{apiBaseUrl}</code>.</p>
          <p className="section-status">{connectionError}</p>
          <label className="field-stack">
            <span>Host URL</span>
            <input
              value={apiBaseUrlDraft}
              onChange={(event) => setApiBaseUrlDraft(event.currentTarget.value)}
              placeholder="http://10.0.0.5:8000"
            />
          </label>
          <div className="button-row">
            <button type="button" className="secondary-button" onClick={() => void handleSaveApiBaseUrl()}>
              Save host
            </button>
            <button type="button" className="primary-button" onClick={() => void refreshWorkspace({ withLoading: true, reason: "reconnect" })}>
              Retry connection
            </button>
            <button type="button" className="ghost-button" onClick={() => void handleClearApiBaseUrlOverride()}>
              Reset host
            </button>
          </div>
          {apiBaseUrlStatus ? <p className="section-status">{apiBaseUrlStatus}</p> : null}
          <p className="section-status">
            Start the host with <code>python server.py</code>, then retry.
          </p>
        </section>
      </main>
    );
  }

  return (
    <main className={`app-shell ${isMobileSidebarOpen ? "mobile-sidebar-open" : ""}`}>
      {isMobileSidebarOpen ? (
        <button
          type="button"
          className="mobile-sidebar-backdrop"
          aria-label="Close conversations"
          onClick={() => setIsMobileSidebarOpen(false)}
        />
      ) : null}

      <section className="workspace-grid">
        <ConversationSidebar
          conversations={conversations}
          activeConversationId={activeConversationId}
          openConversationMenuId={openConversationMenuId}
          editingConversationId={editingConversationId}
          editingConversationTitle={editingConversationTitle}
          onEditingConversationTitleChange={setEditingConversationTitle}
          onSelectConversation={(conversationId) => void handleSelectConversation(conversationId)}
          onCreateConversation={() => void handleCreateConversation()}
          onToggleConversationMenu={handleToggleConversationMenu}
          onStartRenameConversation={handleStartRenameConversation}
          onCancelRenameConversation={handleCancelRenameConversation}
          onRenameConversationSubmit={(event, conversationId) => void handleRenameConversationSubmit(event, conversationId)}
          onClearConversation={(conversationId) => void handleClearConversation(conversationId)}
          onDeleteConversation={(conversationId) => void handleDeleteConversation(conversationId)}
          isMobileOpen={isMobileSidebarOpen}
          onCloseMobile={() => setIsMobileSidebarOpen(false)}
        />

        <ChatWorkspace
          activeConversationTitle={historyTitle(conversations, activeConversationId)}
          history={history}
          messageListRef={messageListRef}
          chatStatus={chatStatus}
          connectionState={connectionState}
          connectionSummary={connectionSummary}
          lastConnectionError={lastConnectionError}
          replyAudioStatus={replyAudioStatus}
          latestReplyAudioReady={Boolean(latestReplyAudioUrl)}
          isReplyAudioPlaying={isReplyAudioPlaying}
          chatInput={chatInput}
          sending={sending}
          currentListenerStatus={currentListenerStatus}
          isListening={Boolean(status?.listening)}
          backendChoices={llmOptions?.backend_choices ?? []}
          selectedBackend={selectedBackend}
          selectedModel={selectedModel}
          modelChoices={modelChoices}
          reasoningEffort={reasoningEffort}
          onChatInputChange={setChatInput}
          onStartListener={() => void handleListenerAction("start")}
          onPauseListener={() => void handleListenerAction("stop")}
          onShutdownListener={() => void handleListenerAction("shutdown")}
          onSelectedBackendChange={handleSelectedBackendChange}
          onSelectedModelChange={setSelectedModel}
          onReasoningEffortChange={setReasoningEffort}
          onComposerKeyDown={handleComposerKeyDown}
          onSendMessage={() => void handleSendMessage()}
          remoteVoiceAvailable={remoteVoiceCapability.available}
          remoteVoiceBusy={isRemoteTranscribing}
          remoteVoiceDisabledReason={remoteVoiceCapability.reason}
          remoteVoiceStatus={remoteVoiceStatus}
          isRemoteRecording={isRemoteRecording}
          remoteRecordingElapsedLabel={remoteRecordingElapsedLabel}
          remoteVoicePressToTalk={remoteVoicePressToTalk}
          speakRepliesOnThisDevice={speakRepliesOnThisDevice}
          onToggleRemoteVoice={() => void handleRemoteVoiceToggle()}
          onRemoteVoicePressStart={handleRemoteVoicePressStart}
          onRemoteVoicePressEnd={handleRemoteVoicePressEnd}
          onRemoteVoicePressCancel={handleRemoteVoicePressCancel}
          onPlayLatestReplyAudio={() => void handlePlayLatestReplyAudio()}
          onToggleSpeakRepliesOnThisDevice={handleToggleSpeakRepliesOnThisDevice}
          onReconnectHost={() => void handleReconnectHost()}
          onOpenConversationSidebar={() => setIsMobileSidebarOpen(true)}
          onOpenSettings={() => {
            setActiveInspectorSection("assistant");
            setIsSettingsOpen(true);
          }}
        />
      </section>

      <SettingsOverlay
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        apiBaseUrl={apiBaseUrl}
        apiBaseUrlDraft={apiBaseUrlDraft}
        onApiBaseUrlDraftChange={setApiBaseUrlDraft}
        onSaveApiBaseUrl={() => void handleSaveApiBaseUrl()}
        onClearApiBaseUrl={() => void handleClearApiBaseUrlOverride()}
        apiBaseUrlStatus={apiBaseUrlStatus}
        currentListenerStatus={currentListenerStatus}
        currentModel={llmOptions?.current_model ?? "Unknown"}
        currentBackend={llmOptions?.current_backend ?? "Unknown"}
        activeInspectorSection={activeInspectorSection}
        onSectionChange={setActiveInspectorSection}
        onRefreshWorkspace={() => void refreshWorkspace({ withLoading: false, reason: "manual" })}
        onReconnectHost={() => void handleReconnectHost()}
        llmOptions={llmOptions}
        selectedBackend={selectedBackend}
        selectedModel={selectedModel}
        onSelectedBackendChange={handleSelectedBackendChange}
        onSelectedModelChange={setSelectedModel}
        onRefreshLlmSettings={() => void handleRefreshLlmSettings()}
        onApplyLlmSettings={() => void handleApplyLlmSettings()}
        llmStatus={llmStatus}
        audioDevices={audioDevices}
        selectedDeviceIndex={selectedDeviceIndex}
        onSelectAudioDevice={(index) => void handleSelectAudioDevice(index)}
        onListenerAction={(action) => void handleListenerAction(action)}
        isListening={Boolean(status?.listening)}
        deviceStatus={deviceStatus}
        remoteVoiceAvailable={remoteVoiceCapability.available}
        remoteVoiceDisabledReason={remoteVoiceCapability.reason}
        remoteVoiceStatus={remoteVoiceStatus}
        isRemoteRecording={isRemoteRecording}
        isRemoteTranscribing={isRemoteTranscribing}
        remoteRecordingElapsedLabel={remoteRecordingElapsedLabel}
        remoteVoicePressToTalk={remoteVoicePressToTalk}
        onToggleRemoteVoice={() => void handleRemoteVoiceToggle()}
        speakRepliesOnThisDevice={speakRepliesOnThisDevice}
        onToggleSpeakRepliesOnThisDevice={handleToggleSpeakRepliesOnThisDevice}
        replyAudioStatus={replyAudioStatus}
        latestReplyAudioReady={Boolean(latestReplyAudioUrl)}
        isReplyAudioPlaying={isReplyAudioPlaying}
        onPlayLatestReplyAudio={() => void handlePlayLatestReplyAudio()}
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
        notificationStatus={notificationStatus}
        notificationSyncing={notificationSyncing}
        scheduledReminderCount={scheduledReminderCount}
        lastNotificationSyncLabel={lastNotificationSyncLabel}
        onSetNotificationsEnabled={(value) => void setNotificationsEnabled(value)}
        onRequestNotificationsPermission={() => void requestNotificationsPermission()}
        onSyncNotifications={() => void syncReminderNotifications()}
        onSendTestNotification={() => void sendTestNotification()}
        profile={profile}
        onProfileChange={setProfile}
        onSaveProfile={(event) => void handleSaveProfile(event)}
        profileStatus={profileStatus}
        live={live}
      />
    </main>
  );
}

export default App;
