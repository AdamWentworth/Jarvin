import type { ChatMode, ConversationSummary, LiveSnapshot, StatusResponse, UserProfilePayload } from "./types";

export type InspectorSection = "assistant" | "voice" | "profile" | "diagnostics";
export type ReasoningEffort = "low" | "medium" | "high" | "extra_high";

export const MODE_OPTIONS: Array<{ value: ChatMode; label: string }> = [
  {
    value: "voice_fast",
    label: "Voice Fast",
  },
  {
    value: "chat_balanced",
    label: "Chat Balanced",
  },
  {
    value: "agent_strong",
    label: "Agent Strong",
  },
];

export const REASONING_OPTIONS: Array<{ value: ReasoningEffort; label: string }> = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "extra_high", label: "Extra High" },
];

export const INSPECTOR_SECTIONS: Array<{ value: InspectorSection; label: string }> = [
  { value: "assistant", label: "Assistant" },
  { value: "voice", label: "Voice" },
  { value: "profile", label: "Profile" },
  { value: "diagnostics", label: "Diagnostics" },
];

export const DEFAULT_PROFILE: UserProfilePayload = {
  name: "",
  goal: "",
  mood: "Focused",
  communication_style: "Friendly",
  response_length: "Balanced",
};

export const MOOD_OPTIONS = ["Focused", "Stressed", "Curious", "Relaxed", "Tired", "Creative", "Problem-Solving"];
export const COMMUNICATION_STYLE_OPTIONS = ["Friendly", "Professional", "Casual", "Encouraging", "Direct"];
export const RESPONSE_LENGTH_OPTIONS = ["Concise", "Balanced", "Detailed"];

export function statusLabel(status: StatusResponse | null, live: LiveSnapshot | null): string {
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

export function historyTitle(conversations: ConversationSummary[], activeConversationId: number | null): string {
  const active = conversations.find((item) => item.id === activeConversationId);
  return active?.title ?? "New conversation";
}

export function reasoningToChatMode(reasoning: ReasoningEffort): ChatMode {
  switch (reasoning) {
    case "low":
      return "voice_fast";
    case "medium":
      return "chat_balanced";
    case "high":
      return "agent_strong";
    case "extra_high":
      return "agent_strong";
  }
}
