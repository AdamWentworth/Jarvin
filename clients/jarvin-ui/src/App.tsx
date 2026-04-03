import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
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
  ChatMode,
  ConversationSummary,
  ConversationTurn,
  ConversationWorkspaceResponse,
  LLMOptionsResponse,
  LiveSnapshot,
  StatusResponse,
  UserProfilePayload,
  WorkspaceBootstrapResponse,
} from "./lib/types";

const MODE_OPTIONS: Array<{ value: ChatMode; label: string; hint: string }> = [
  {
    value: "voice_fast",
    label: "Voice Fast",
    hint: "Short, speakable replies for quick back-and-forth.",
  },
  {
    value: "chat_balanced",
    label: "Chat Balanced",
    hint: "The best default for everyday local chat on this machine.",
  },
  {
    value: "agent_strong",
    label: "Agent Strong",
    hint: "Longer, more structured answers for planning and task work.",
  },
];

const DEFAULT_PROFILE: UserProfilePayload = {
  name: "",
  goal: "",
  mood: "Focused",
  communication_style: "Friendly",
  response_length: "Balanced",
};

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong.";
}

function statusLabel(status: StatusResponse | null, live: LiveSnapshot | null): string {
  if (!status?.listening) {
    return "Stopped";
  }
  if (live?.recording) {
    return "Recording";
  }
  if (live?.processing) {
    return "Processing";
  }
  return "Listening";
}

function historyTitle(conversations: ConversationSummary[], activeConversationId: number | null): string {
  const active = conversations.find((item) => item.id === activeConversationId);
  return active?.title ?? "New conversation";
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
  const [chatMode, setChatMode] = useState<ChatMode>("chat_balanced");
  const [renameDraft, setRenameDraft] = useState("");
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
  const [chatStatus, setChatStatus] = useState("Host-connected typed chat is ready.");
  const [llmStatus, setLlmStatus] = useState("");
  const [profileStatus, setProfileStatus] = useState("");
  const [deviceStatus, setDeviceStatus] = useState("");
  const lastLiveSeq = useRef<number | null>(null);

  const activeConversation = useMemo(
    () => conversations.find((item) => item.id === activeConversationId) ?? null,
    [activeConversationId, conversations],
  );

  const activeModeHint = useMemo(
    () => MODE_OPTIONS.find((item) => item.value === chatMode)?.hint ?? "",
    [chatMode],
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
      setRenameDraft(historyTitle(workspace.conversations, workspace.active_conversation_id));
      setLlmOptions(llm);
      setSelectedBackend(llm.current_backend);
      setSelectedModel(llm.current_model);
      setLlmStatus(llm.message ?? "");
      setAudioDevices(devices);
      setSelectedDeviceIndex(devices.selected_index ?? "");
      setStatus(currentStatus);
      setLive(currentLive);
      lastLiveSeq.current = currentLive.seq ?? null;
      setChatStatus("Connected to the local Jarvin host.");
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
    setRenameDraft(activeConversation?.title ?? "");
  }, [activeConversation?.id, activeConversation?.title]);

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

  async function handleRenameConversation() {
    if (!activeConversationId) {
      return;
    }
    const nextTitle = renameDraft.trim();
    if (!nextTitle) {
      setChatStatus("Give the conversation a title first.");
      return;
    }
    try {
      const workspace = await renameConversation(activeConversationId, nextTitle);
      syncWorkspaceState(setConversations, setActiveConversationId, setHistory, workspace);
      setChatStatus("Conversation renamed.");
    } catch (error) {
      setChatStatus(describeError(error));
    }
  }

  async function handleClearConversation() {
    if (!activeConversationId) {
      return;
    }
    if (!window.confirm("Clear the current conversation history?")) {
      return;
    }
    try {
      const workspace = await clearConversation(activeConversationId);
      syncWorkspaceState(setConversations, setActiveConversationId, setHistory, workspace);
      setChatStatus("Conversation history cleared.");
    } catch (error) {
      setChatStatus(describeError(error));
    }
  }

  async function handleDeleteConversation() {
    if (!activeConversationId) {
      return;
    }
    if (!window.confirm("Delete this conversation?")) {
      return;
    }
    try {
      const workspace = await deleteConversation(activeConversationId);
      syncWorkspaceState(setConversations, setActiveConversationId, setHistory, workspace);
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
    setChatStatus(`Thinking in ${MODE_OPTIONS.find((item) => item.value === chatMode)?.label ?? "Chat"} mode...`);
    try {
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
      setChatStatus(`Reply ready in ${MODE_OPTIONS.find((item) => item.value === response.mode_used)?.label ?? response.mode_used}.`);
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

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSendMessage();
    }
  }

  if (loading) {
    return (
      <main className="app-shell loading-shell">
        <section className="loading-card">
          <div className="loading-badge">Desktop Shell</div>
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
          <div className="loading-badge">Host Unreachable</div>
          <h1>Jarvin is not answering yet</h1>
          <p>The desktop client could not reach the host at <code>{getApiBaseUrl()}</code>.</p>
          <p className="error-copy">{connectionError}</p>
          <div className="loading-actions">
            <button type="button" onClick={() => void refreshWorkspace()}>
              Retry connection
            </button>
          </div>
          <p className="loading-hint">Start the host with <code>python server.py</code>, then retry.</p>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <section className="brand-card">
          <div className="eyebrow">Jarvin Desktop</div>
          <h1>Desktop shell for the host-run assistant</h1>
          <p>
            This client talks to the local FastAPI host over HTTP so the same UI architecture can later move to Tauri mobile.
          </p>
        </section>

        <section className="utility-card">
          <div className="utility-line">
            <div>
              <div className="utility-label">Host</div>
              <div className="utility-value">{getApiBaseUrl()}</div>
            </div>
            <div className={`status-pill status-${statusLabel(status, live).toLowerCase()}`}>
              {statusLabel(status, live)}
            </div>
          </div>

          <div className="utility-actions">
            <button
              type="button"
              className="start-button"
              onClick={() => void handleListenerAction("start")}
              disabled={status?.listening}
            >
              Start
            </button>
            <button
              type="button"
              className="pause-button"
              onClick={() => void handleListenerAction("stop")}
              disabled={!status?.listening}
            >
              Pause
            </button>
            <button type="button" className="danger-button" onClick={() => void handleListenerAction("shutdown")}>
              Shutdown
            </button>
          </div>

          <div className="utility-meta">
            <span>Model: {llmOptions?.current_model ?? "Unknown"}</span>
            <span>Backend: {llmOptions?.current_backend ?? "Unknown"}</span>
          </div>
        </section>
      </header>

      <section className="workspace-grid">
        <aside className="sidebar-card">
          <div className="sidebar-header">
            <div>
              <div className="eyebrow">Conversations</div>
              <h2>Workspace history</h2>
            </div>
            <button type="button" onClick={() => void handleCreateConversation()}>
              New chat
            </button>
          </div>

          <div className="conversation-list">
            {conversations.map((conversation) => (
              <button
                type="button"
                key={conversation.id}
                className={`conversation-item ${conversation.id === activeConversationId ? "active" : ""}`}
                onClick={() => void handleSelectConversation(conversation.id)}
              >
                <span className="conversation-title">{conversation.title}</span>
                <span className="conversation-meta">{conversation.messages} messages</span>
              </button>
            ))}
          </div>

          <div className="sidebar-footer">
            <label className="field-label" htmlFor="rename-conversation">
              Rename selected chat
            </label>
            <input
              id="rename-conversation"
              value={renameDraft}
              onChange={(event) => setRenameDraft(event.currentTarget.value)}
              placeholder="Conversation title"
            />
            <div className="sidebar-actions">
              <button type="button" onClick={() => void handleRenameConversation()} disabled={!activeConversationId}>
                Rename
              </button>
              <button type="button" onClick={() => void handleClearConversation()} disabled={!activeConversationId}>
                Clear
              </button>
              <button type="button" className="danger-button" onClick={() => void handleDeleteConversation()} disabled={!activeConversationId}>
                Delete
              </button>
            </div>
          </div>
        </aside>

        <section className="main-card">
          <div className="conversation-header">
            <div>
              <div className="eyebrow">Active conversation</div>
              <h2>{historyTitle(conversations, activeConversationId)}</h2>
            </div>
            <div className="conversation-header-meta">
              <span>{statusLabel(status, live)}</span>
              <span>{live?.cycle_ms ? `${live.cycle_ms} ms cycle` : "Idle"}</span>
            </div>
          </div>

          <div className="chat-shell">
            <div className="message-list">
              {history.length === 0 ? (
                <div className="empty-state">
                  <h3>Ready for typed chat</h3>
                  <p>Start a conversation here while the host keeps the models and GPU local.</p>
                </div>
              ) : (
                history.map((turn, index) => (
                  <article key={`${turn.role}-${index}`} className={`message-row ${turn.role === "user" ? "user" : "assistant"}`}>
                    <div className="message-card">
                      <div className="message-role">{turn.role === "user" ? "You" : "Jarvin"}</div>
                      <div className="message-text">{turn.message}</div>
                    </div>
                  </article>
                ))
              )}
            </div>

            <div className="composer-shell">
              <div className="composer-status">{chatStatus}</div>
              <textarea
                value={chatInput}
                onChange={(event) => setChatInput(event.currentTarget.value)}
                onKeyDown={handleComposerKeyDown}
                placeholder="Message Jarvin. Press Enter to send, Shift+Enter for a new line."
              />

              <div className="composer-actions">
                <label className="mode-select">
                  <span>Mode</span>
                  <select value={chatMode} onChange={(event) => setChatMode(event.currentTarget.value as ChatMode)}>
                    {MODE_OPTIONS.map((mode) => (
                      <option key={mode.value} value={mode.value}>
                        {mode.label}
                      </option>
                    ))}
                  </select>
                </label>

                <button type="button" className="send-button" onClick={() => void handleSendMessage()} disabled={sending || !chatInput.trim()}>
                  {sending ? "Sending..." : "Send message"}
                </button>
              </div>

              <div className="mode-hint">{activeModeHint}</div>

              <div className="settings-stack">
                <details className="settings-panel">
                  <summary>Model &amp; Backend</summary>
                  <div className="settings-body">
                    <label>
                      <span>Backend</span>
                      <select
                        value={selectedBackend}
                        onChange={(event) => {
                          setSelectedBackend(event.currentTarget.value);
                          const nextChoices =
                            event.currentTarget.value === "ollama_http"
                              ? llmOptions?.ollama_model_choices ?? []
                              : llmOptions?.local_model_choices ?? [];
                          setSelectedModel(nextChoices[0]?.value ?? "");
                        }}
                      >
                        {(llmOptions?.backend_choices ?? []).map((choice) => (
                          <option key={choice.value} value={choice.value}>
                            {choice.label}
                          </option>
                        ))}
                      </select>
                    </label>

                    <label>
                      <span>Model</span>
                      <select value={selectedModel} onChange={(event) => setSelectedModel(event.currentTarget.value)}>
                        {modelChoices.map((choice) => (
                          <option key={choice.value} value={choice.value}>
                            {choice.label}
                          </option>
                        ))}
                      </select>
                    </label>

                    <div className="settings-actions">
                      <button type="button" onClick={() => void handleRefreshLlmSettings()}>
                        Refresh models
                      </button>
                      <button type="button" onClick={() => void handleApplyLlmSettings()}>
                        Apply
                      </button>
                    </div>

                    <p className="settings-status">{llmStatus || "Host model settings will appear here."}</p>
                  </div>
                </details>

                <details className="settings-panel">
                  <summary>Voice &amp; Devices</summary>
                  <div className="settings-body">
                    <label>
                      <span>Input device</span>
                      <select
                        value={selectedDeviceIndex}
                        onChange={(event) => void handleSelectAudioDevice(Number(event.currentTarget.value))}
                      >
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
                    <p className="settings-status">
                      {deviceStatus ||
                        (audioDevices?.selected_name
                          ? `Current input: [${audioDevices.selected_index}] ${audioDevices.selected_name}`
                          : "No input device selected.")}
                    </p>
                  </div>
                </details>

                <details className="settings-panel">
                  <summary>Profile &amp; Personalization</summary>
                  <div className="settings-body">
                    <form className="profile-form" onSubmit={(event) => void handleSaveProfile(event)}>
                      <label>
                        <span>Name</span>
                        <input
                          value={profile.name}
                          onChange={(event) => setProfile((current) => ({ ...current, name: event.currentTarget.value }))}
                          placeholder="Your name"
                        />
                      </label>
                      <label>
                        <span>Goal</span>
                        <input
                          value={profile.goal}
                          onChange={(event) => setProfile((current) => ({ ...current, goal: event.currentTarget.value }))}
                          placeholder="Current goal"
                        />
                      </label>
                      <label>
                        <span>Mood</span>
                        <select
                          value={profile.mood}
                          onChange={(event) => setProfile((current) => ({ ...current, mood: event.currentTarget.value }))}
                        >
                          {["Focused", "Stressed", "Curious", "Relaxed", "Tired", "Creative", "Problem-Solving"].map((item) => (
                            <option key={item} value={item}>
                              {item}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        <span>Communication style</span>
                        <select
                          value={profile.communication_style}
                          onChange={(event) =>
                            setProfile((current) => ({ ...current, communication_style: event.currentTarget.value }))
                          }
                        >
                          {["Friendly", "Professional", "Casual", "Encouraging", "Direct"].map((item) => (
                            <option key={item} value={item}>
                              {item}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        <span>Response length</span>
                        <select
                          value={profile.response_length}
                          onChange={(event) =>
                            setProfile((current) => ({ ...current, response_length: event.currentTarget.value }))
                          }
                        >
                          {["Concise", "Balanced", "Detailed"].map((item) => (
                            <option key={item} value={item}>
                              {item}
                            </option>
                          ))}
                        </select>
                      </label>
                      <div className="settings-actions">
                        <button type="submit">Save profile</button>
                      </div>
                    </form>
                    <p className="settings-status">{profileStatus || "Saved profile preferences will live on the host."}</p>
                  </div>
                </details>

                <details className="settings-panel">
                  <summary>Diagnostics</summary>
                  <div className="settings-body">
                    <div className="diagnostic-grid">
                      <div>
                        <span>Listener state</span>
                        <strong>{statusLabel(status, live)}</strong>
                      </div>
                      <div>
                        <span>Last transcript</span>
                        <strong>{live?.transcript || "None yet"}</strong>
                      </div>
                      <div>
                        <span>Last reply</span>
                        <strong>{live?.reply || "None yet"}</strong>
                      </div>
                      <div>
                        <span>Timing</span>
                        <strong>
                          {live?.cycle_ms ? `${live.cycle_ms} ms cycle` : "Waiting for activity"}
                          {live?.utter_ms ? ` | ${live.utter_ms} ms utterance` : ""}
                        </strong>
                      </div>
                    </div>
                  </div>
                </details>
              </div>
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}

export default App;
