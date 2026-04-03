import type {
  AudioDevicesResponse,
  AudioSelectResponse,
  ChatMode,
  ChatResponse,
  ConversationWorkspaceResponse,
  LLMOptionsResponse,
  LiveSnapshot,
  StatusResponse,
  UserProfilePayload,
  WorkspaceBootstrapResponse,
} from "./types";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export function getApiBaseUrl(): string {
  const raw = import.meta.env.VITE_JARVIN_API_BASE_URL ?? DEFAULT_API_BASE_URL;
  return raw.replace(/\/+$/, "");
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  const text = await response.text();
  const body = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const detail =
      (body && typeof body === "object" && "detail" in body && String(body.detail)) ||
      (body && typeof body === "object" && "error" in body && String(body.error)) ||
      (body && typeof body === "object" && "message" in body && String(body.message)) ||
      response.statusText ||
      "Request failed";
    throw new ApiError(detail, response.status, body);
  }

  return body as T;
}

export function getWorkspaceBootstrap() {
  return requestJson<WorkspaceBootstrapResponse>("/workspace/bootstrap");
}

export function getStatus() {
  return requestJson<StatusResponse>("/status");
}

export function getLive() {
  return requestJson<LiveSnapshot>("/live");
}

export function startListener() {
  return requestJson<{ ok: boolean; message: string }>("/start", { method: "POST" });
}

export function stopListener() {
  return requestJson<{ ok: boolean; message: string }>("/stop", { method: "POST" });
}

export function shutdownHost() {
  return requestJson<{ ok: boolean; message: string }>("/shutdown", { method: "POST" });
}

export function getLlmOptions() {
  return requestJson<LLMOptionsResponse>("/llm/options");
}

export function applyLlmSelection(backend: string, model: string) {
  return requestJson<LLMOptionsResponse>("/llm/select", {
    method: "POST",
    body: JSON.stringify({ backend, model, load_now: true }),
  });
}

export function getAudioDevices() {
  return requestJson<AudioDevicesResponse>("/audio/devices");
}

export function selectAudioDevice(index: number) {
  return requestJson<AudioSelectResponse>("/audio/select", {
    method: "POST",
    body: JSON.stringify({ index, restart: true }),
  });
}

export function saveProfile(profile: UserProfilePayload) {
  return requestJson<UserProfilePayload>("/profile", {
    method: "PUT",
    body: JSON.stringify(profile),
  });
}

export function createConversation(title?: string) {
  return requestJson<ConversationWorkspaceResponse>("/conversations", {
    method: "POST",
    body: JSON.stringify({ title: title ?? null }),
  });
}

export function activateConversation(conversationId: number) {
  return requestJson<ConversationWorkspaceResponse>(`/conversations/${conversationId}/activate`, {
    method: "POST",
  });
}

export function renameConversation(conversationId: number, title: string) {
  return requestJson<ConversationWorkspaceResponse>(`/conversations/${conversationId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export function clearConversation(conversationId: number) {
  return requestJson<ConversationWorkspaceResponse>(`/conversations/${conversationId}/clear`, {
    method: "POST",
  });
}

export function deleteConversation(conversationId: number) {
  return requestJson<ConversationWorkspaceResponse>(`/conversations/${conversationId}`, {
    method: "DELETE",
  });
}

export function sendChatMessage(params: {
  userText: string;
  conversationId: number | null;
  mode: ChatMode;
}) {
  return requestJson<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({
      user_text: params.userText,
      conversation_id: params.conversationId,
      mode: params.mode,
      use_history: true,
      use_profile: true,
    }),
  });
}
