import type { AgentAccessMode, ChatMode, ConversationSummary, LiveSnapshot, StatusResponse, UserProfilePayload } from "./types";

export type InspectorSection = "general" | "voice" | "notifications" | "profile" | "diagnostics";
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

export const AGENT_ACCESS_OPTIONS: Array<{ value: AgentAccessMode; label: string; hint: string }> = [
  {
    value: "read_only",
    label: "Read only",
    hint: "Jarvin can inspect and research, but not change files or run host commands.",
  },
  {
    value: "approve_risky",
    label: "Approve risky actions",
    hint: "Jarvin can prepare writes and commands, then wait for your approval.",
  },
  {
    value: "full_access",
    label: "Trusted host tool access",
    hint: "Jarvin can immediately run the currently allowed host commands and workspace writes from this client.",
  },
];

export const INSPECTOR_SECTIONS: Array<{ value: InspectorSection; label: string }> = [
  { value: "general", label: "General" },
  { value: "voice", label: "Voice" },
  { value: "notifications", label: "Notifications" },
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
