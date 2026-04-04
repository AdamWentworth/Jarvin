import type {
  AudioDevicesResponse,
  AudioSelectResponse,
  ChatMode,
  ChatResponse,
  ConversationWorkspaceResponse,
  HealthResponse,
  LLMOptionsResponse,
  LiveSnapshot,
  StatusResponse,
  TranscribeResponse,
  UserProfilePayload,
  WorkspaceBootstrapResponse,
} from "./types";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
const API_BASE_URL_STORAGE_KEY = "jarvin.apiBaseUrl";

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

function normalizeApiBaseUrl(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) {
    return "";
  }

  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    throw new Error("Enter a full host URL such as http://10.0.0.5:8000");
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("Host URL must start with http:// or https://");
  }

  return parsed.origin;
}

function describeNetworkError(error: unknown, fallback: string): Error {
  if (error instanceof Error) {
    return new Error(error.message || fallback);
  }
  return new Error(fallback);
}

function canUseStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export function getStoredApiBaseUrl(): string | null {
  if (!canUseStorage()) {
    return null;
  }

  const raw = window.localStorage.getItem(API_BASE_URL_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    const normalized = normalizeApiBaseUrl(raw);
    return normalized || null;
  } catch {
    window.localStorage.removeItem(API_BASE_URL_STORAGE_KEY);
    return null;
  }
}

export function setStoredApiBaseUrl(raw: string): string {
  const normalized = normalizeApiBaseUrl(raw);
  if (!normalized) {
    throw new Error("Enter a full host URL such as http://10.0.0.5:8000");
  }

  if (canUseStorage()) {
    window.localStorage.setItem(API_BASE_URL_STORAGE_KEY, normalized);
  }
  return normalized;
}

export function clearStoredApiBaseUrl() {
  if (canUseStorage()) {
    window.localStorage.removeItem(API_BASE_URL_STORAGE_KEY);
  }
}

export function getApiBaseUrl(): string {
  const explicit = import.meta.env.VITE_JARVIN_API_BASE_URL;
  if (explicit) {
    return normalizeApiBaseUrl(explicit);
  }

  const stored = getStoredApiBaseUrl();
  if (stored) {
    return stored;
  }

  if (
    typeof window !== "undefined" &&
    (window.location.protocol === "http:" || window.location.protocol === "https:") &&
    window.location.pathname.startsWith("/app")
  ) {
    return normalizeApiBaseUrl(window.location.origin);
  }

  return normalizeApiBaseUrl(DEFAULT_API_BASE_URL);
}

export function buildApiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  return `${getApiBaseUrl()}${path.startsWith("/") ? path : `/${path}`}`;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      ...init,
    });
  } catch (error) {
    throw describeNetworkError(error, `Could not reach the Jarvin host at ${getApiBaseUrl()}.`);
  }

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

export function getHealth() {
  return requestJson<HealthResponse>("/healthz");
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
  speakReply: boolean;
}) {
  return requestJson<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({
      user_text: params.userText,
      conversation_id: params.conversationId,
      mode: params.mode,
      use_history: true,
      use_profile: true,
      speak_reply: params.speakReply,
    }),
  });
}

async function blobToBase64(blob: Blob): Promise<string> {
  return await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Could not read the recorded audio on this device."));
    reader.onload = () => {
      if (typeof reader.result !== "string") {
        reject(new Error("Could not prepare the recorded audio for upload."));
        return;
      }

      const [, base64] = reader.result.split(",", 2);
      if (!base64) {
        reject(new Error("Could not encode the recorded audio for upload."));
        return;
      }
      resolve(base64);
    };
    reader.readAsDataURL(blob);
  });
}

async function transcribeAudioBlobViaJson(blob: Blob, filename: string) {
  const audioBase64 = await blobToBase64(blob);
  const body = await requestJson<TranscribeResponse & { error?: string }>("/transcribe-bytes", {
    method: "POST",
    body: JSON.stringify({
      audio_base64: audioBase64,
      content_type: blob.type || null,
      filename,
    }),
  });

  if (body && typeof body === "object" && "error" in body && body.error) {
    throw new Error(String(body.error));
  }

  return body;
}

export async function transcribeAudioBlob(blob: Blob, filename = "remote-input.webm") {
  const form = new FormData();
  form.append("audio_file", blob, filename);

  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/transcribe`, {
      method: "POST",
      body: form,
    });
  } catch {
    return await transcribeAudioBlobViaJson(blob, filename);
  }

  const text = await response.text();
  const body = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const detail =
      (body && typeof body === "object" && "detail" in body && String(body.detail)) ||
      (body && typeof body === "object" && "error" in body && String(body.error)) ||
      response.statusText ||
      "Transcription failed";
    throw new ApiError(detail, response.status, body);
  }

  if (body && typeof body === "object" && "error" in body && body.error) {
    throw new ApiError(String(body.error), response.status, body);
  }

  return body as TranscribeResponse;
}
