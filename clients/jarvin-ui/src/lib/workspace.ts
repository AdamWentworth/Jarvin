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
