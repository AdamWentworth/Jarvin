import type { Dispatch, MutableRefObject, SetStateAction } from "react";

import { transcribeAudioBlob } from "./api";
import type { AgentAccessMode, VoiceTranscriptReview } from "./types";

export type RemoteVoiceCapability = {
  available: boolean;
  reason: string;
};

export type ConnectionState = "connecting" | "connected" | "degraded" | "offline";
export type PipelineStageState = "idle" | "working" | "done" | "error";
export type SendSource = "typed" | "remote_voice";
export type PendingVoiceReview = {
  heardText: string;
  candidateText: string;
  review: VoiceTranscriptReview;
};

export type RemoteVoiceDiagnostics = {
  microphone: PipelineStageState;
  upload: PipelineStageState;
  transcription: PipelineStageState;
  chat: PipelineStageState;
  playback: PipelineStageState;
  note: string;
};

export const REMOTE_RECORDING_LIMIT_SECONDS = 90;

export const DEFAULT_REMOTE_VOICE_DIAGNOSTICS: RemoteVoiceDiagnostics = {
  microphone: "idle",
  upload: "idle",
  transcription: "idle",
  chat: "idle",
  playback: "idle",
  note: "",
};

const SPEAK_REPLIES_STORAGE_KEY = "jarvin.speakRepliesOnDevice";
const CHAT_DRAFT_STORAGE_PREFIX = "jarvin.chatDraft.";
const AGENT_ACCESS_MODE_STORAGE_KEY = "jarvin.agentAccessMode";

export function detectRemoteVoiceCapability(): RemoteVoiceCapability {
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

export function detectMobileClient(): boolean {
  if (typeof navigator === "undefined") {
    return false;
  }
  return /android|iphone|ipad|ipod/i.test(navigator.userAgent);
}

export function getStoredSpeakRepliesPreference(): boolean {
  if (typeof window === "undefined" || typeof window.localStorage === "undefined") {
    return detectMobileClient();
  }

  const raw = window.localStorage.getItem(SPEAK_REPLIES_STORAGE_KEY);
  if (raw === null) {
    return detectMobileClient();
  }
  return raw === "true";
}

export function setStoredSpeakRepliesPreference(value: boolean) {
  if (typeof window !== "undefined" && typeof window.localStorage !== "undefined") {
    window.localStorage.setItem(SPEAK_REPLIES_STORAGE_KEY, String(value));
  }
}

export function getStoredAgentAccessMode(): AgentAccessMode {
  if (!canUseWindowStorage()) {
    return "approve_risky";
  }
  const raw = window.localStorage.getItem(AGENT_ACCESS_MODE_STORAGE_KEY);
  if (raw === "read_only" || raw === "approve_risky" || raw === "full_access") {
    return raw;
  }
  return "approve_risky";
}

export function setStoredAgentAccessMode(value: AgentAccessMode) {
  if (!canUseWindowStorage()) {
    return;
  }
  window.localStorage.setItem(AGENT_ACCESS_MODE_STORAGE_KEY, value);
}

function canUseWindowStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function chatDraftStorageKey(conversationId: number | null): string {
  return `${CHAT_DRAFT_STORAGE_PREFIX}${conversationId ?? "new"}`;
}

export function getStoredChatDraft(conversationId: number | null): string {
  if (!canUseWindowStorage()) {
    return "";
  }
  return window.localStorage.getItem(chatDraftStorageKey(conversationId)) ?? "";
}

export function setStoredChatDraft(conversationId: number | null, value: string) {
  if (!canUseWindowStorage()) {
    return;
  }
  const key = chatDraftStorageKey(conversationId);
  if (value) {
    window.localStorage.setItem(key, value);
  } else {
    window.localStorage.removeItem(key);
  }
}

export function formatTimestamp(timestamp: string | null): string {
  if (!timestamp) {
    return "Never";
  }

  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) {
    return timestamp;
  }

  return parsed.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });
}

export function formatDuration(seconds: number): string {
  const clamped = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(clamped / 60);
  const remainingSeconds = clamped % 60;
  return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
}

export function stageLabel(state: PipelineStageState): string {
  switch (state) {
    case "working":
      return "Working";
    case "done":
      return "Done";
    case "error":
      return "Error";
    default:
      return "Idle";
  }
}

export function connectionLabel(state: ConnectionState): string {
  switch (state) {
    case "connected":
      return "Connected";
    case "degraded":
      return "Reconnecting";
    case "offline":
      return "Offline";
    default:
      return "Connecting";
  }
}

export function withRecorderStop(recorder: MediaRecorder) {
  try {
    recorder.stop();
  } catch {
    // ignore invalid stop calls during teardown
  }
}

export function stopRemoteStream(streamRef: MutableRefObject<MediaStream | null>) {
  const stream = streamRef.current;
  if (stream) {
    for (const track of stream.getTracks()) {
      track.stop();
    }
  }
  streamRef.current = null;
}

export async function finalizeRemoteRecording({
  mediaChunksRef,
  mediaRecorderRef,
  mediaStreamRef,
  setIsRemoteRecording,
  setIsRemoteTranscribing,
  setRemoteVoiceStatus,
  setRemoteVoiceDiagnostics,
  setPendingVoiceReview,
  sendMessage,
}: {
  mediaChunksRef: MutableRefObject<Blob[]>;
  mediaRecorderRef: MutableRefObject<MediaRecorder | null>;
  mediaStreamRef: MutableRefObject<MediaStream | null>;
  setIsRemoteRecording: (value: boolean) => void;
  setIsRemoteTranscribing: (value: boolean) => void;
  setRemoteVoiceStatus: (value: string) => void;
  setRemoteVoiceDiagnostics: Dispatch<SetStateAction<RemoteVoiceDiagnostics>>;
  setPendingVoiceReview: (value: PendingVoiceReview | null) => void;
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
    setRemoteVoiceDiagnostics((current) => ({
      ...current,
      microphone: "error",
      note: "The microphone stopped, but no remote audio was captured.",
    }));
    setRemoteVoiceStatus("No remote audio was captured.");
    return;
  }

  try {
    setIsRemoteTranscribing(true);
    setRemoteVoiceDiagnostics((current) => ({
      ...current,
      microphone: "done",
      upload: "working",
      transcription: "idle",
      note: "Uploading the recorded audio to the Jarvin host.",
    }));
    setRemoteVoiceStatus("Transcribing remote audio...");
    const response = await transcribeAudioBlob(blob, `remote-input.${mimeType.includes("mp4") ? "m4a" : "webm"}`);
    setRemoteVoiceDiagnostics((current) => ({
      ...current,
      upload: "done",
      transcription: "done",
      note: "Remote audio uploaded and transcribed successfully.",
    }));
    const text = response.transcribed_text.trim();
    if (!text) {
      setRemoteVoiceDiagnostics((current) => ({
        ...current,
        transcription: "error",
        note: "The host did not detect speech in the uploaded audio.",
      }));
      setRemoteVoiceStatus("No speech detected in the remote audio.");
      return;
    }

    const review = response.review ?? null;
    const suggestedText = review?.suggested_text?.trim() ?? "";
    const action = review?.action ?? "accept";

    if (action === "confirm" || action === "repeat") {
      const clarificationMessage =
        review?.clarification_message?.trim() ||
        (action === "repeat"
          ? "That transcription does not look reliable enough to act on. Please repeat it."
          : `I heard "${text}". Does that look right before I act on it?`);
      setPendingVoiceReview({
        heardText: text,
        candidateText: suggestedText || text,
        review: {
          confidence_level: review?.confidence_level ?? "medium",
          confidence_score: review?.confidence_score ?? (action === "repeat" ? 0.25 : 0.6),
          action,
          suggested_text: suggestedText || null,
          clarification_message: clarificationMessage,
          review_reason: review?.review_reason ?? null,
        },
      });
      setRemoteVoiceDiagnostics((current) => ({
        ...current,
        chat: "idle",
        note: clarificationMessage,
      }));
      setRemoteVoiceStatus(clarificationMessage);
      return;
    }

    const messageText = suggestedText && suggestedText !== text ? suggestedText : text;
    setPendingVoiceReview(null);
    setRemoteVoiceStatus(
      messageText === text ? `Heard: ${text}` : `Heard: ${text}. Using: ${messageText}`,
    );
    await sendMessage(messageText);
  } catch (error) {
    const message = error instanceof Error && error.message ? error.message : "Remote voice input failed.";
    setRemoteVoiceDiagnostics((current) => ({
      ...current,
      upload: current.upload === "working" ? "error" : current.upload,
      transcription: current.transcription === "working" || current.transcription === "idle" ? "error" : current.transcription,
      note: message,
    }));
    if (error instanceof Error && error.message) {
      setRemoteVoiceStatus(error.message);
    } else {
      setRemoteVoiceStatus("Remote voice input failed.");
    }
  } finally {
    setIsRemoteTranscribing(false);
  }
}
