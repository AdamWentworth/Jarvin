import { useEffect, useMemo, useRef, useState } from "react";
import {
  activateConversation,
  applyLlmSelection,
  clearStoredApiBaseUrl,
  getAgentActionLog,
  getApiBaseUrl,
  getAudioDevices,
  getHealth,
  getLive,
  getLlmOptions,
  getStatus,
  getStoredApiBaseUrl,
  selectAudioDevice,
  setStoredApiBaseUrl,
  shutdownHost,
  startListener,
  stopListener,
  subscribeToLiveStream,
  getWorkspaceBootstrap,
} from "../lib/api";
import type {
  AgentActionLogItem,
  AudioDevicesResponse,
  HealthResponse,
  LLMOptionsResponse,
  LiveSnapshot,
  StatusResponse,
} from "../lib/types";
import { connectionLabel, formatTimestamp, type ConnectionState } from "../lib/runtime";
import { statusLabel } from "../lib/ui";

type WorkspacePayload = Awaited<ReturnType<typeof getWorkspaceBootstrap>>;
type ConversationWorkspacePayload = Awaited<ReturnType<typeof activateConversation>>;

type UseJarvinHostOptions = {
  activeConversationId: number | null;
  describeError: (error: unknown) => string;
  onWorkspaceSync: (workspace: WorkspacePayload | ConversationWorkspacePayload) => void;
  reportError: (message: string) => void;
  sending: boolean;
  shouldPollConversation: boolean;
};

export function useJarvinHost({
  activeConversationId,
  describeError,
  onWorkspaceSync,
  reportError,
  sending,
  shouldPollConversation,
}: UseJarvinHostOptions) {
  const describeErrorRef = useRef(describeError);
  const onWorkspaceSyncRef = useRef(onWorkspaceSync);
  const reportErrorRef = useRef(reportError);
  const apiBaseUrl = getApiBaseUrl();
  const [llmOptions, setLlmOptions] = useState<LLMOptionsResponse | null>(null);
  const [selectedBackend, setSelectedBackend] = useState("llama_cpp");
  const [selectedModel, setSelectedModel] = useState("");
  const [audioDevices, setAudioDevices] = useState<AudioDevicesResponse | null>(null);
  const [selectedDeviceIndex, setSelectedDeviceIndex] = useState<number | "">("");
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [live, setLive] = useState<LiveSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [isClientOnline, setIsClientOnline] = useState<boolean>(() => (typeof navigator === "undefined" ? true : navigator.onLine));
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");
  const [lastConnectionError, setLastConnectionError] = useState("");
  const [lastSuccessfulContactAt, setLastSuccessfulContactAt] = useState<string | null>(null);
  const [lastRoundTripMs, setLastRoundTripMs] = useState<number | null>(null);
  const [connectionError, setConnectionError] = useState("");
  const [apiBaseUrlDraft, setApiBaseUrlDraft] = useState<string>(() => getStoredApiBaseUrl() ?? getApiBaseUrl());
  const [apiBaseUrlStatus, setApiBaseUrlStatus] = useState("");
  const [llmStatus, setLlmStatus] = useState("");
  const [deviceStatus, setDeviceStatus] = useState("");
  const [agentActionLog, setAgentActionLog] = useState<AgentActionLogItem[]>([]);
  const [agentActionLogStatus, setAgentActionLogStatus] = useState("");
  const lastLiveSeq = useRef<number | null>(null);
  const lastLiveRev = useRef<number | null>(null);
  const consecutivePollFailuresRef = useRef(0);
  const conversationRefreshInFlightRef = useRef(false);
  const liveStreamConnectedRef = useRef(false);
  const activeConversationIdRef = useRef(activeConversationId);
  const sendingRef = useRef(sending);
  const shouldPollConversationRef = useRef(shouldPollConversation);

  useEffect(() => {
    describeErrorRef.current = describeError;
    onWorkspaceSyncRef.current = onWorkspaceSync;
    reportErrorRef.current = reportError;
  }, [describeError, onWorkspaceSync, reportError]);

  useEffect(() => {
    activeConversationIdRef.current = activeConversationId;
    sendingRef.current = sending;
    shouldPollConversationRef.current = shouldPollConversation;
  }, [activeConversationId, sending, shouldPollConversation]);

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
        return `${base} | ${lastRoundTripMs} ms`;
      }
      return base;
    }
    if (lastConnectionError) {
      return `${base} | ${lastConnectionError}`;
    }
    return base;
  }, [connectionState, isClientOnline, lastConnectionError, lastRoundTripMs]);

  const lastSuccessfulContactLabel = useMemo(
    () => formatTimestamp(lastSuccessfulContactAt),
    [lastSuccessfulContactAt],
  );

  const modelChoices = useMemo(() => {
    if (!llmOptions) {
      return [];
    }
    return selectedBackend === "ollama_http" ? llmOptions.ollama_model_choices : llmOptions.local_model_choices;
  }, [llmOptions, selectedBackend]);

  function applyLiveSnapshot(snapshot: LiveSnapshot, options?: { updateContact?: boolean }) {
    const updateContact = options?.updateContact ?? true;
    setLive(snapshot);
    lastLiveSeq.current = snapshot.seq ?? null;
    lastLiveRev.current = snapshot.rev ?? null;
    if (updateContact) {
      setConnectionState("connected");
      setLastConnectionError("");
      setLastSuccessfulContactAt(new Date().toISOString());
    }
  }

  async function refreshActiveConversation(options?: { refreshActionLog?: boolean }) {
    const conversationId = activeConversationIdRef.current;
    if (conversationId === null || sendingRef.current || conversationRefreshInFlightRef.current) {
      return;
    }

    conversationRefreshInFlightRef.current = true;
    try {
      const workspace = await activateConversation(conversationId);
      onWorkspaceSyncRef.current(workspace);
      if (options?.refreshActionLog) {
        void refreshAgentActionLog(conversationId);
      }
    } finally {
      conversationRefreshInFlightRef.current = false;
    }
  }

  async function handleIncomingLiveSnapshot(snapshot: LiveSnapshot, options?: { updateContact?: boolean }) {
    const updateContact = options?.updateContact ?? true;
    const nextRev = snapshot.rev ?? null;
    if (nextRev !== null && nextRev === lastLiveRev.current) {
      return;
    }

    const previousSeq = lastLiveSeq.current;
    applyLiveSnapshot(snapshot, { updateContact });

    const eventConversationId =
      typeof snapshot.event_conversation_id === "number" ? snapshot.event_conversation_id : null;
    const activeConversationId = activeConversationIdRef.current;
    const eventMatchesActiveConversation =
      activeConversationId !== null &&
      (eventConversationId === null || eventConversationId === activeConversationId);
    const sequenceChanged = snapshot.seq !== null && snapshot.seq !== previousSeq;
    const shouldRefreshConversation =
      eventMatchesActiveConversation &&
      !sendingRef.current &&
      (sequenceChanged ||
        shouldPollConversationRef.current ||
        snapshot.event_kind === "conversation" ||
        snapshot.event_kind === "agent_action");

    if (shouldRefreshConversation) {
      await refreshActiveConversation({ refreshActionLog: true });
      return;
    }

    if (snapshot.event_kind === "agent_action" && eventMatchesActiveConversation) {
      void refreshAgentActionLog(activeConversationId);
    }
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

      onWorkspaceSyncRef.current(workspace);
      setLlmOptions(llm);
      setSelectedBackend(llm.current_backend);
      setSelectedModel(llm.current_model);
      setLlmStatus(llm.message ?? "");
      setAudioDevices(devices);
      setSelectedDeviceIndex(devices.selected_index ?? "");
      setHealth(currentHealth);
      setStatus(currentStatus);
      applyLiveSnapshot(currentLive, { updateContact: false });
      setApiBaseUrlStatus("");
      setConnectionState("connected");
      setLastConnectionError("");
      setLastSuccessfulContactAt(new Date().toISOString());
      setLastRoundTripMs(Math.max(1, Math.round((typeof performance !== "undefined" ? performance.now() : Date.now()) - startedAt)));
      consecutivePollFailuresRef.current = 0;
      void refreshAgentActionLog().catch(() => {
        // Keep the main workspace bootstrap healthy even if diagnostics cannot load.
      });
    } catch (error) {
      const message = describeErrorRef.current(error);
      setConnectionError(message);
      setLastConnectionError(message);
      setConnectionState("offline");
    } finally {
      if (withLoading) {
        setLoading(false);
      }
    }
  }

  async function refreshAgentActionLog(conversationId?: number | null) {
    try {
      const next = await getAgentActionLog(40, conversationId);
      setAgentActionLog(next.actions);
      setAgentActionLogStatus("");
    } catch (error) {
      setAgentActionLog([]);
      setAgentActionLogStatus(describeErrorRef.current(error));
    }
  }

  useEffect(() => {
    void refreshWorkspace({ withLoading: true, reason: "initial" });
  }, []);

  useEffect(() => {
    const available = modelChoices.map((item) => item.value);
    if (selectedModel && available.includes(selectedModel)) {
      return;
    }
    setSelectedModel(available[0] ?? "");
  }, [modelChoices, selectedModel]);

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
    if (!isClientOnline) {
      liveStreamConnectedRef.current = false;
      return undefined;
    }

    let cleanup = () => {};
    try {
      cleanup = subscribeToLiveStream({
        onOpen: () => {
          liveStreamConnectedRef.current = true;
          consecutivePollFailuresRef.current = 0;
          setConnectionState("connected");
          setLastConnectionError("");
          setLastSuccessfulContactAt(new Date().toISOString());
        },
        onMessage: (snapshot) => {
          void handleIncomingLiveSnapshot(snapshot);
        },
        onError: (error) => {
          liveStreamConnectedRef.current = false;
          const message =
            error instanceof Error
              ? error.message
              : "Live stream interrupted. Falling back to direct polling while it reconnects.";
          setLastConnectionError(message);
          setConnectionState("degraded");
        },
      });
    } catch (error) {
      liveStreamConnectedRef.current = false;
      setLastConnectionError(describeErrorRef.current(error));
      setConnectionState("degraded");
    }

    return () => {
      liveStreamConnectedRef.current = false;
      cleanup();
    };
  }, [apiBaseUrl, isClientOnline]);

  useEffect(() => {
    const poll = window.setInterval(async () => {
      try {
        const startedAt = typeof performance !== "undefined" ? performance.now() : Date.now();
        const [currentHealth, currentStatus] = await Promise.all([getHealth(), getStatus()]);
        setHealth(currentHealth);
        setStatus(currentStatus);
        setLastRoundTripMs(Math.max(1, Math.round((typeof performance !== "undefined" ? performance.now() : Date.now()) - startedAt)));

        if (!liveStreamConnectedRef.current) {
          const currentLive = await getLive();
          await handleIncomingLiveSnapshot(currentLive);
        } else {
          setConnectionState("connected");
          setLastConnectionError("");
          setLastSuccessfulContactAt(new Date().toISOString());
        }

        consecutivePollFailuresRef.current = 0;
      } catch (error) {
        consecutivePollFailuresRef.current += 1;
        setLastConnectionError(describeErrorRef.current(error));
        setConnectionState(consecutivePollFailuresRef.current >= 3 ? "offline" : "degraded");
      }
    }, 5000);

    return () => window.clearInterval(poll);
  }, []);

  async function handleReconnectHost() {
    setApiBaseUrlStatus("Reconnecting to the Jarvin host...");
    await refreshWorkspace({ withLoading: false, reason: "reconnect" });
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
      setLlmStatus(describeErrorRef.current(error));
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
      setLlmStatus(describeErrorRef.current(error));
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
      setDeviceStatus(describeErrorRef.current(error));
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
      reportErrorRef.current(describeErrorRef.current(error));
    }
  }

  async function handleSaveApiBaseUrl() {
    try {
      const next = setStoredApiBaseUrl(apiBaseUrlDraft);
      setApiBaseUrlDraft(next);
      setApiBaseUrlStatus("Saved host URL. Trying connection...");
      await refreshWorkspace({ withLoading: false, reason: "reconnect" });
    } catch (error) {
      setApiBaseUrlStatus(describeErrorRef.current(error));
    }
  }

  async function handleClearApiBaseUrlOverride() {
    clearStoredApiBaseUrl();
    const next = getApiBaseUrl();
    setApiBaseUrlDraft(next);
    setApiBaseUrlStatus("Using the default host URL again.");
    await refreshWorkspace({ withLoading: false, reason: "reconnect" });
  }

  function handleSelectedBackendChange(value: string) {
    setSelectedBackend(value);
    const nextChoices = value === "ollama_http" ? llmOptions?.ollama_model_choices ?? [] : llmOptions?.local_model_choices ?? [];
    setSelectedModel(nextChoices[0]?.value ?? "");
  }

  return {
    apiBaseUrl,
    apiBaseUrlDraft,
    apiBaseUrlStatus,
    agentActionLog,
    agentActionLogStatus,
    audioDevices,
    connectionError,
    connectionState,
    connectionSummary,
    currentListenerStatus,
    deviceStatus,
    handleApplyLlmSettings,
    handleClearApiBaseUrlOverride,
    handleListenerAction,
    handleReconnectHost,
    handleRefreshLlmSettings,
    handleSaveApiBaseUrl,
    handleSelectedBackendChange,
    handleSelectAudioDevice,
    health,
    isClientOnline,
    lastConnectionError,
    lastRoundTripMs,
    lastSuccessfulContactAt,
    lastSuccessfulContactLabel,
    llmOptions,
    llmStatus,
    live,
    loading,
    modelChoices,
    refreshAgentActionLog,
    refreshWorkspace,
    selectedBackend,
    selectedDeviceIndex,
    selectedModel,
    setApiBaseUrlDraft,
    setSelectedModel,
    status,
  };
}
