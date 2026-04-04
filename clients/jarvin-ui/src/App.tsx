import { FormEvent, KeyboardEvent as ReactKeyboardEvent, MouseEvent, useEffect, useMemo, useRef, useState } from "react";
import "./App.css";
import {
  ApiError,
  activateConversation,
  applyLlmSelection,
  clearConversation,
  createConversation,
  deleteConversation,
  getApiBaseUrl,
  getAudioDevices,
  getLive,
  getLlmOptions,
  getStatus,
  getWorkspaceBootstrap,
  renameConversation,
  saveProfile,
  selectAudioDevice,
  sendChatMessage,
  shutdownHost,
  startListener,
  stopListener,
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
  const [chatStatus, setChatStatus] = useState("");
  const [llmStatus, setLlmStatus] = useState("");
  const [profileStatus, setProfileStatus] = useState("");
  const [deviceStatus, setDeviceStatus] = useState("");
  const [openConversationMenuId, setOpenConversationMenuId] = useState<number | null>(null);
  const [editingConversationId, setEditingConversationId] = useState<number | null>(null);
  const [editingConversationTitle, setEditingConversationTitle] = useState("");
  const [activeInspectorSection, setActiveInspectorSection] = useState<InspectorSection>("assistant");
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const lastLiveSeq = useRef<number | null>(null);
  const messageListRef = useRef<HTMLDivElement | null>(null);

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

  async function handleSelectConversation(conversationId: number) {
    setOpenConversationMenuId(null);
    setEditingConversationId(null);
    setChatStatus("Loading conversation...");
    try {
      const workspace = await activateConversation(conversationId);
      syncWorkspaceState(setConversations, setActiveConversationId, setHistory, workspace);
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

  async function handleSendMessage() {
    const text = chatInput.trim();
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
      });
      const nextConversationId = response.conversation_id ?? conversationId;
      if (nextConversationId === null) {
        throw new Error("Jarvin did not return a conversation id for this reply.");
      }
      const workspace = await activateConversation(nextConversationId);
      syncWorkspaceState(setConversations, setActiveConversationId, setHistory, workspace);
      setChatInput("");
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
          <div className="eyebrow">Desktop Shell</div>
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
          <div className="button-row">
            <button type="button" className="primary-button" onClick={() => void refreshWorkspace()}>
              Retry connection
            </button>
          </div>
          <p className="section-status">
            Start the host with <code>python server.py</code>, then retry.
          </p>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
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
        />

        <ChatWorkspace
          activeConversationTitle={historyTitle(conversations, activeConversationId)}
          history={history}
          messageListRef={messageListRef}
          chatStatus={chatStatus}
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
