import { FormEvent, KeyboardEvent as ReactKeyboardEvent, MouseEvent, useEffect, useMemo, useRef, useState, type MutableRefObject } from "react";
import "./App.css";
import {
  ApiError,
  activateConversation,
  applyLlmSelection,
  buildApiUrl,
  clearStoredApiBaseUrl,
  clearConversation,
  createConversation,
  deleteConversation,
  getApiBaseUrl,
  getAudioDevices,
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
  transcribeAudioBlob,
} from "./lib/api";
import type {
  AudioDevicesResponse,
  ConversationSummary,
  ConversationTurn,
  ConversationWorkspaceResponse,
  LLMOptionsResponse,
  LiveSnapshot,
  StatusResponse,
  UserProfilePayload,
  WorkspaceBootstrapResponse,
} from "./lib/types";
import {
  DEFAULT_PROFILE,
  historyTitle,
  reasoningToChatMode,
  statusLabel,
  type InspectorSection,
  type ReasoningEffort,
} from "./lib/ui";
import { ConversationSidebar } from "./components/ConversationSidebar";
import { ChatWorkspace } from "./components/ChatWorkspace";
import { SettingsOverlay } from "./components/SettingsOverlay";

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong.";
}

function syncWorkspaceState(
  setConversations: (items: ConversationSummary[]) => void,
  setActiveConversationId: (id: number | null) => void,
  setHistory: (items: ConversationTurn[]) => void,
  data: ConversationWorkspaceResponse | WorkspaceBootstrapResponse,
) {
  setConversations(data.conversations);
  setActiveConversationId(data.active_conversation_id);
  setHistory(data.history);
}

type RemoteVoiceCapability = {
  available: boolean;
  reason: string;
};

function detectRemoteVoiceCapability(): RemoteVoiceCapability {
  if (typeof window === "undefined") {
    return { available: false, reason: "Remote microphone capture is only available in a browser or app shell." };
  }

  if (!window.isSecureContext) {
    return { available: false, reason: "Remote microphone capture needs HTTPS or a Tauri mobile shell." };
  }

  if (!navigator.mediaDevices?.getUserMedia) {
    return { available: false, reason: "This client does not expose microphone access." };
  }

  if (typeof MediaRecorder === "undefined") {
    return { available: false, reason: "This client does not support in-browser audio recording." };
  }

  return { available: true, reason: "" };
}

const SPEAK_REPLIES_STORAGE_KEY = "jarvin.speakRepliesOnDevice";

function detectMobileClient(): boolean {
  if (typeof navigator === "undefined") {
    return false;
  }
  return /android|iphone|ipad|ipod/i.test(navigator.userAgent);
}

function getStoredSpeakRepliesPreference(): boolean {
  if (typeof window === "undefined" || typeof window.localStorage === "undefined") {
    return detectMobileClient();
  }

  const raw = window.localStorage.getItem(SPEAK_REPLIES_STORAGE_KEY);
  if (raw === null) {
    return detectMobileClient();
  }
  return raw === "true";
}

function setStoredSpeakRepliesPreference(value: boolean) {
  if (typeof window !== "undefined" && typeof window.localStorage !== "undefined") {
    window.localStorage.setItem(SPEAK_REPLIES_STORAGE_KEY, String(value));
  }
}

function App() {
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
  const [live, setLive] = useState<LiveSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [connectionError, setConnectionError] = useState("");
  const [apiBaseUrlDraft, setApiBaseUrlDraft] = useState<string>(() => getStoredApiBaseUrl() ?? getApiBaseUrl());
  const [apiBaseUrlStatus, setApiBaseUrlStatus] = useState("");
  const [chatStatus, setChatStatus] = useState("");
  const [replyAudioStatus, setReplyAudioStatus] = useState("");
  const [latestReplyAudioUrl, setLatestReplyAudioUrl] = useState<string | null>(null);
  const [isReplyAudioPlaying, setIsReplyAudioPlaying] = useState(false);
  const [speakRepliesOnThisDevice, setSpeakRepliesOnThisDevice] = useState<boolean>(() => getStoredSpeakRepliesPreference());
  const [llmStatus, setLlmStatus] = useState("");
  const [profileStatus, setProfileStatus] = useState("");
  const [deviceStatus, setDeviceStatus] = useState("");
  const [remoteVoiceStatus, setRemoteVoiceStatus] = useState("");
  const [isRemoteRecording, setIsRemoteRecording] = useState(false);
  const [isRemoteTranscribing, setIsRemoteTranscribing] = useState(false);
  const [openConversationMenuId, setOpenConversationMenuId] = useState<number | null>(null);
  const [editingConversationId, setEditingConversationId] = useState<number | null>(null);
  const [editingConversationTitle, setEditingConversationTitle] = useState("");
  const [activeInspectorSection, setActiveInspectorSection] = useState<InspectorSection>("assistant");
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const lastLiveSeq = useRef<number | null>(null);
  const messageListRef = useRef<HTMLDivElement | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const mediaChunksRef = useRef<Blob[]>([]);
  const replyAudioRef = useRef<HTMLAudioElement | null>(null);

  const remoteVoiceCapability = useMemo(
    () => detectRemoteVoiceCapability(),
    [],
  );

  const currentListenerStatus = useMemo(
    () => statusLabel(status, live),
    [status, live],
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

  async function refreshWorkspace() {
    setLoading(true);
    setConnectionError("");
    try {
      const [workspace, llm, devices, currentStatus, currentLive] = await Promise.all([
        getWorkspaceBootstrap(),
        getLlmOptions(),
        getAudioDevices(),
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
      setStatus(currentStatus);
      setLive(currentLive);
      lastLiveSeq.current = currentLive.seq ?? null;
      setChatStatus("");
      setApiBaseUrlStatus("");
    } catch (error) {
      setConnectionError(describeError(error));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshWorkspace();
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
        const [currentStatus, currentLive] = await Promise.all([getStatus(), getLive()]);
        setStatus(currentStatus);
        setLive(currentLive);

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
      } catch {
        // Keep the desktop shell responsive if the host is briefly unavailable.
      }
    }, 1000);

    return () => window.clearInterval(poll);
  }, [activeConversationId, sending]);

  useEffect(() => {
    return () => {
      const recorder = mediaRecorderRef.current;
      if (recorder && recorder.state !== "inactive") {
        recorder.onstop = null;
        withRecorderStop(recorder);
      }
      stopRemoteStream(mediaStreamRef);
      const replyAudio = replyAudioRef.current;
      if (replyAudio) {
        replyAudio.pause();
        replyAudioRef.current = null;
      }
    };
  }, []);

  async function playReplyAudio(url: string) {
    const absoluteUrl = buildApiUrl(url);
    const currentAudio = replyAudioRef.current;
    if (currentAudio) {
      currentAudio.pause();
      currentAudio.currentTime = 0;
    }

    const audio = new Audio(absoluteUrl);
    audio.preload = "auto";
    replyAudioRef.current = audio;

    audio.onended = () => {
      setIsReplyAudioPlaying(false);
      setReplyAudioStatus("");
    };

    audio.onerror = () => {
      setIsReplyAudioPlaying(false);
      setReplyAudioStatus("Reply audio could not be played on this device.");
    };

    try {
      setIsReplyAudioPlaying(true);
      setReplyAudioStatus("Playing Jarvin's reply...");
      await audio.play();
    } catch (error) {
      setIsReplyAudioPlaying(false);
      setReplyAudioStatus(describeError(error) || "Reply audio is ready. Tap play to hear it.");
      throw error;
    }
  }

  function handleToggleSpeakRepliesOnThisDevice() {
    setSpeakRepliesOnThisDevice((current) => {
      const next = !current;
      setStoredSpeakRepliesPreference(next);
      if (!next) {
        const audio = replyAudioRef.current;
        if (audio) {
          audio.pause();
          audio.currentTime = 0;
        }
        setIsReplyAudioPlaying(false);
      }
      setReplyAudioStatus(next ? "Jarvin will speak replies on this device when audio is available." : "");
      return next;
    });
  }

  async function handlePlayLatestReplyAudio() {
    if (!latestReplyAudioUrl) {
      setReplyAudioStatus("No reply audio is ready yet.");
      return;
    }

    try {
      await playReplyAudio(latestReplyAudioUrl);
    } catch {
      // Status is already updated inside playReplyAudio.
    }
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

  async function handleSendMessage(rawText?: string) {
    const text = (rawText ?? chatInput).trim();
    if (!text || sending) {
      return;
    }

    let conversationId = activeConversationId;
    if (conversationId === null) {
      try {
        const workspace = await createConversation();
        syncWorkspaceState(setConversations, setActiveConversationId, setHistory, workspace);
        conversationId = workspace.active_conversation_id;
      } catch (error) {
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
        if (speakRepliesOnThisDevice) {
          try {
            await playReplyAudio(response.tts_url);
          } catch {
            setReplyAudioStatus("Reply audio is ready. Tap play to hear it on this device.");
          }
        } else {
          setReplyAudioStatus("Reply audio is ready.");
        }
      } else {
        setLatestReplyAudioUrl(null);
        setReplyAudioStatus(speakRepliesOnThisDevice ? "Reply audio was not available for this response." : "");
      }
      setChatStatus("");
    } catch (error) {
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
      await refreshWorkspace();
    } catch (error) {
      setApiBaseUrlStatus(describeError(error));
    }
  }

  async function handleClearApiBaseUrlOverride() {
    clearStoredApiBaseUrl();
    const next = getApiBaseUrl();
    setApiBaseUrlDraft(next);
    setApiBaseUrlStatus("Using the default host URL again.");
    await refreshWorkspace();
  }

  async function handleRemoteVoiceToggle() {
    if (!remoteVoiceCapability.available) {
      setRemoteVoiceStatus(remoteVoiceCapability.reason);
      return;
    }

    if (isRemoteTranscribing || sending) {
      return;
    }

    const activeRecorder = mediaRecorderRef.current;
    if (activeRecorder && activeRecorder.state !== "inactive") {
      setRemoteVoiceStatus("Finishing remote capture...");
      withRecorderStop(activeRecorder);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaStreamRef.current = stream;
      mediaRecorderRef.current = recorder;
      mediaChunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          mediaChunksRef.current.push(event.data);
        }
      };

      recorder.onerror = () => {
        setRemoteVoiceStatus("Remote microphone capture failed.");
        setIsRemoteRecording(false);
        mediaRecorderRef.current = null;
        mediaChunksRef.current = [];
        stopRemoteStream(mediaStreamRef);
      };

      recorder.onstop = () => {
        void finalizeRemoteRecording({
          mediaChunksRef,
          mediaRecorderRef,
          mediaStreamRef,
          setIsRemoteRecording,
          setIsRemoteTranscribing,
          setRemoteVoiceStatus,
          sendMessage: (text) => handleSendMessage(text),
        });
      };

      recorder.start();
      setRemoteVoiceStatus("Listening on this device. Tap again to send.");
      setIsRemoteRecording(true);
    } catch (error) {
      setRemoteVoiceStatus(describeError(error) || "Microphone permission was denied.");
    }
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
          <p>The desktop client could not reach the host at <code>{getApiBaseUrl()}</code>.</p>
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
            <button type="button" className="primary-button" onClick={() => void refreshWorkspace()}>
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
          speakRepliesOnThisDevice={speakRepliesOnThisDevice}
          onToggleRemoteVoice={() => void handleRemoteVoiceToggle()}
          onPlayLatestReplyAudio={() => void handlePlayLatestReplyAudio()}
          onToggleSpeakRepliesOnThisDevice={handleToggleSpeakRepliesOnThisDevice}
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
        apiBaseUrl={getApiBaseUrl()}
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
        onRefreshWorkspace={() => void refreshWorkspace()}
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
        onToggleRemoteVoice={() => void handleRemoteVoiceToggle()}
        speakRepliesOnThisDevice={speakRepliesOnThisDevice}
        onToggleSpeakRepliesOnThisDevice={handleToggleSpeakRepliesOnThisDevice}
        replyAudioStatus={replyAudioStatus}
        latestReplyAudioReady={Boolean(latestReplyAudioUrl)}
        isReplyAudioPlaying={isReplyAudioPlaying}
        onPlayLatestReplyAudio={() => void handlePlayLatestReplyAudio()}
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

function withRecorderStop(recorder: MediaRecorder) {
  try {
    recorder.stop();
  } catch {
    // ignore invalid stop calls during teardown
  }
}

function stopRemoteStream(streamRef: MutableRefObject<MediaStream | null>) {
  const stream = streamRef.current;
  if (stream) {
    for (const track of stream.getTracks()) {
      track.stop();
    }
  }
  streamRef.current = null;
}

async function finalizeRemoteRecording({
  mediaChunksRef,
  mediaRecorderRef,
  mediaStreamRef,
  setIsRemoteRecording,
  setIsRemoteTranscribing,
  setRemoteVoiceStatus,
  sendMessage,
}: {
  mediaChunksRef: MutableRefObject<Blob[]>;
  mediaRecorderRef: MutableRefObject<MediaRecorder | null>;
  mediaStreamRef: MutableRefObject<MediaStream | null>;
  setIsRemoteRecording: (value: boolean) => void;
  setIsRemoteTranscribing: (value: boolean) => void;
  setRemoteVoiceStatus: (value: string) => void;
  sendMessage: (text: string) => Promise<void>;
}) {
  const recorder = mediaRecorderRef.current;
  const mimeType = recorder?.mimeType || mediaChunksRef.current[0]?.type || "audio/webm";
  const blob = new Blob(mediaChunksRef.current, { type: mimeType });

  mediaRecorderRef.current = null;
  mediaChunksRef.current = [];
  setIsRemoteRecording(false);
  stopRemoteStream(mediaStreamRef);

  if (blob.size === 0) {
    setRemoteVoiceStatus("No remote audio was captured.");
    return;
  }

  try {
    setIsRemoteTranscribing(true);
    setRemoteVoiceStatus("Transcribing remote audio...");
    const response = await transcribeAudioBlob(blob, `remote-input.${mimeType.includes("mp4") ? "m4a" : "webm"}`);
    const text = response.transcribed_text.trim();
    if (!text) {
      setRemoteVoiceStatus("No speech detected in the remote audio.");
      return;
    }

    setRemoteVoiceStatus(`Heard: ${text}`);
    await sendMessage(text);
  } catch (error) {
    if (error instanceof Error && error.message) {
      setRemoteVoiceStatus(error.message);
    } else {
      setRemoteVoiceStatus("Remote voice input failed.");
    }
  } finally {
    setIsRemoteTranscribing(false);
  }
}
