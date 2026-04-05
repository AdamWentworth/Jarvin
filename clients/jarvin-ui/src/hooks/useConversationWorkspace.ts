import { FormEvent, MouseEvent, useEffect, useState } from "react";
import {
  activateConversation,
  clearConversation,
  createConversation,
  deleteConversation,
  getWorkspaceBootstrap,
  renameConversation,
} from "../lib/api";
import type { ConversationSummary, ConversationTurn, UserProfilePayload } from "../lib/types";
import { syncWorkspaceState } from "../lib/workspace";

type BootstrapWorkspacePayload = Awaited<ReturnType<typeof getWorkspaceBootstrap>>;
type ConversationWorkspacePayload = Awaited<ReturnType<typeof activateConversation>>;
type WorkspacePayload = BootstrapWorkspacePayload | ConversationWorkspacePayload;

type UseConversationWorkspaceOptions = {
  describeError: (error: unknown) => string;
  onProfileSync: (profile: UserProfilePayload) => void;
  onStatusChange: (message: string) => void;
  onChatInputReset: () => void;
  onCloseMobileSidebar: () => void;
};

export function useConversationWorkspace({
  describeError,
  onProfileSync,
  onStatusChange,
  onChatInputReset,
  onCloseMobileSidebar,
}: UseConversationWorkspaceOptions) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);
  const [history, setHistory] = useState<ConversationTurn[]>([]);
  const [openConversationMenuId, setOpenConversationMenuId] = useState<number | null>(null);
  const [editingConversationId, setEditingConversationId] = useState<number | null>(null);
  const [editingConversationTitle, setEditingConversationTitle] = useState("");

  useEffect(() => {
    if (editingConversationId === null) {
      return;
    }
    const match = conversations.find((item) => item.id === editingConversationId);
    if (!match) {
      setEditingConversationId(null);
      setEditingConversationTitle("");
    }
  }, [conversations, editingConversationId]);

  function syncWorkspace(workspace: WorkspacePayload) {
    syncWorkspaceState(setConversations, setActiveConversationId, setHistory, workspace);
    if ("profile" in workspace) {
      onProfileSync(workspace.profile);
    }
  }

  async function refreshConversationWorkspace() {
    const workspace = await getWorkspaceBootstrap();
    syncWorkspace(workspace);
  }

  async function handleSelectConversation(conversationId: number) {
    setOpenConversationMenuId(null);
    setEditingConversationId(null);
    onStatusChange("Loading conversation...");
    try {
      const workspace = await activateConversation(conversationId);
      syncWorkspace(workspace);
      onCloseMobileSidebar();
      onStatusChange("Conversation ready.");
    } catch (error) {
      onStatusChange(describeError(error));
    }
  }

  async function handleCreateConversation() {
    setOpenConversationMenuId(null);
    setEditingConversationId(null);
    setEditingConversationTitle("");
    onStatusChange("Creating a fresh workspace...");
    try {
      const workspace = await createConversation();
      syncWorkspace(workspace);
      onChatInputReset();
      onCloseMobileSidebar();
      onStatusChange("Fresh chat ready.");
    } catch (error) {
      onStatusChange(describeError(error));
    }
  }

  function handleToggleConversationMenu(event: MouseEvent<HTMLButtonElement>, conversationId: number) {
    event.stopPropagation();
    setEditingConversationId(null);
    setEditingConversationTitle("");
    setOpenConversationMenuId((current) => (current === conversationId ? null : conversationId));
  }

  function handleStartRenameConversation(event: MouseEvent<HTMLButtonElement>, conversation: ConversationSummary) {
    event.stopPropagation();
    setOpenConversationMenuId(null);
    setEditingConversationId(conversation.id);
    setEditingConversationTitle(conversation.title);
  }

  function handleCancelRenameConversation() {
    setEditingConversationId(null);
    setEditingConversationTitle("");
  }

  async function handleRenameConversationSubmit(event: FormEvent<HTMLFormElement>, conversationId: number) {
    event.preventDefault();
    const nextTitle = editingConversationTitle.trim();
    if (!nextTitle) {
      onStatusChange("Give the conversation a title first.");
      return;
    }
    try {
      await renameConversation(conversationId, nextTitle);
      await refreshConversationWorkspace();
      setEditingConversationId(null);
      setEditingConversationTitle("");
      onStatusChange("Conversation renamed.");
    } catch (error) {
      onStatusChange(describeError(error));
    }
  }

  async function handleClearConversation(conversationId: number) {
    setOpenConversationMenuId(null);
    if (!window.confirm("Clear this conversation history?")) {
      return;
    }
    try {
      await clearConversation(conversationId);
      await refreshConversationWorkspace();
      onStatusChange("Conversation history cleared.");
    } catch (error) {
      onStatusChange(describeError(error));
    }
  }

  async function handleDeleteConversation(conversationId: number) {
    setOpenConversationMenuId(null);
    if (!window.confirm("Delete this conversation?")) {
      return;
    }
    try {
      await deleteConversation(conversationId);
      await refreshConversationWorkspace();
      onStatusChange("Conversation deleted.");
    } catch (error) {
      onStatusChange(describeError(error));
    }
  }

  return {
    activeConversationId,
    conversations,
    editingConversationId,
    editingConversationTitle,
    handleCancelRenameConversation,
    handleClearConversation,
    handleCreateConversation,
    handleDeleteConversation,
    handleRenameConversationSubmit,
    handleSelectConversation,
    handleStartRenameConversation,
    handleToggleConversationMenu,
    history,
    openConversationMenuId,
    setEditingConversationTitle,
    setOpenConversationMenuId,
    syncWorkspace,
  };
}
