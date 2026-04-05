import { useEffect, useMemo, useRef, useState } from "react";
import {
  activateConversation,
  applyLlmSelection,
  clearStoredApiBaseUrl,
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
  getWorkspaceBootstrap,
} from "../lib/api";
import type {
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
};

export function useJarvinHost({
  activeConversationId,
  describeError,
  onWorkspaceSync,
  reportError,
  sending,
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
  const lastLiveSeq = useRef<number | null>(null);
  const consecutivePollFailuresRef = useRef(0);

  useEffect(() => {
    describeErrorRef.current = describeError;
    onWorkspaceSyncRef.current = onWorkspaceSync;
    reportErrorRef.current = reportError;
  }, [describeError, onWorkspaceSync, reportError]);

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

  const modelChoices = useMemo(() => {
    if (!llmOptions) {
      return [];
    }
    return selectedBackend === "ollama_http" ? llmOptions.ollama_model_choices : llmOptions.local_model_choices;
  }, [llmOptions, selectedBackend]);

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
      setLive(currentLive);
      lastLiveSeq.current = currentLive.seq ?? null;
      setApiBaseUrlStatus("");
      setConnectionState("connected");
      setLastConnectionError("");
      setLastSuccessfulContactAt(new Date().toISOString());
      setLastRoundTripMs(Math.max(1, Math.round((typeof performance !== "undefined" ? performance.now() : Date.now()) - startedAt)));
      consecutivePollFailuresRef.current = 0;
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
        if (nextSeq !== null && nextSeq !== lastLiveSeq.current && activeConversationId !== null && !sending) {
          lastLiveSeq.current = nextSeq;
          const workspace = await activateConversation(activeConversationId);
          onWorkspaceSyncRef.current(workspace);
        } else {
          lastLiveSeq.current = nextSeq;
        }
      } catch (error) {
        consecutivePollFailuresRef.current += 1;
        setLastConnectionError(describeErrorRef.current(error));
        setConnectionState(consecutivePollFailuresRef.current >= 3 ? "offline" : "degraded");
      }
    }, 1000);

    return () => window.clearInterval(poll);
  }, [activeConversationId, sending]);

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
    refreshWorkspace,
    selectedBackend,
    selectedDeviceIndex,
    selectedModel,
    setApiBaseUrlDraft,
    setSelectedModel,
    status,
  };
}
