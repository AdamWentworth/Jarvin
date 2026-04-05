import { ApiError } from "./api";
import type {
  ConversationSummary,
  ConversationTurn,
  ConversationWorkspaceResponse,
  WorkspaceBootstrapResponse,
} from "./types";

export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string" && error.trim()) {
    return error;
  }
  if (error && typeof error === "object") {
    const maybeMessage = "message" in error ? (error as { message?: unknown }).message : undefined;
    if (typeof maybeMessage === "string" && maybeMessage.trim()) {
      return maybeMessage;
    }
    try {
      const serialized = JSON.stringify(error);
      if (serialized && serialized !== "{}") {
        return serialized;
      }
    } catch {
      // fall through to generic fallback
    }
  }
  return "Something went wrong.";
}

export function syncWorkspaceState(
  setConversations: (items: ConversationSummary[]) => void,
  setActiveConversationId: (id: number | null) => void,
  setHistory: (items: ConversationTurn[]) => void,
  data: ConversationWorkspaceResponse | WorkspaceBootstrapResponse,
) {
  setConversations(data.conversations);
  setActiveConversationId(data.active_conversation_id);
  setHistory(data.history);
}
