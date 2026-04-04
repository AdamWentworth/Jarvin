import type { FormEvent, MouseEvent } from "react";
import { PencilSquareIcon } from "@heroicons/react/20/solid";
import type { ConversationSummary } from "../lib/types";

type ConversationSidebarProps = {
  conversations: ConversationSummary[];
  activeConversationId: number | null;
  openConversationMenuId: number | null;
  editingConversationId: number | null;
  editingConversationTitle: string;
  onEditingConversationTitleChange: (value: string) => void;
  onSelectConversation: (conversationId: number) => void;
  onCreateConversation: () => void;
  onToggleConversationMenu: (event: MouseEvent<HTMLButtonElement>, conversationId: number) => void;
  onStartRenameConversation: (event: MouseEvent<HTMLButtonElement>, conversation: ConversationSummary) => void;
  onCancelRenameConversation: () => void;
  onRenameConversationSubmit: (event: FormEvent<HTMLFormElement>, conversationId: number) => void;
  onClearConversation: (conversationId: number) => void;
  onDeleteConversation: (conversationId: number) => void;
};

export function ConversationSidebar({
  conversations,
  activeConversationId,
  openConversationMenuId,
  editingConversationId,
  editingConversationTitle,
  onEditingConversationTitleChange,
  onSelectConversation,
  onCreateConversation,
  onToggleConversationMenu,
  onStartRenameConversation,
  onCancelRenameConversation,
  onRenameConversationSubmit,
  onClearConversation,
  onDeleteConversation,
}: ConversationSidebarProps) {
  return (
    <aside className="sidebar-shell">
      <div className="sidebar-top">
        <div className="eyebrow">Conversations</div>

        <button
          type="button"
          className="primary-button new-chat-button"
          aria-label="Start a new chat"
          title="New chat"
          onClick={onCreateConversation}
        >
          <PencilSquareIcon aria-hidden="true" />
        </button>
      </div>

      <nav className="conversation-nav" aria-label="Conversations">
        {conversations.map((conversation) => {
          const isActive = conversation.id === activeConversationId;
          const isEditing = conversation.id === editingConversationId;
          const menuOpen = conversation.id === openConversationMenuId;

          return (
            <div
              key={conversation.id}
              className={`conversation-row ${isActive ? "active" : ""} ${menuOpen ? "menu-open" : ""}`}
            >
              {isEditing ? (
                <form
                  className="conversation-edit-form"
                  onClick={(event) => event.stopPropagation()}
                  onSubmit={(event) => onRenameConversationSubmit(event, conversation.id)}
                >
                  <input
                    value={editingConversationTitle}
                    onChange={(event) => onEditingConversationTitleChange(event.currentTarget.value)}
                    autoFocus
                    placeholder="Conversation title"
                  />
                  <div className="conversation-edit-actions">
                    <button type="submit" className="secondary-button compact-button">
                      Save
                    </button>
                    <button type="button" className="ghost-button compact-button" onClick={onCancelRenameConversation}>
                      Cancel
                    </button>
                  </div>
                </form>
              ) : (
                <>
                  <button
                    type="button"
                    className="conversation-main"
                    onClick={() => onSelectConversation(conversation.id)}
                  >
                    <span className="conversation-title">{conversation.title}</span>
                    <span className="conversation-meta">
                      {conversation.messages} messages
                      {conversation.is_active ? " | active" : ""}
                    </span>
                  </button>

                  <button
                    type="button"
                    className="icon-button conversation-menu-trigger"
                    aria-label={`Conversation actions for ${conversation.title}`}
                    aria-haspopup="menu"
                    aria-expanded={menuOpen}
                    onClick={(event) => onToggleConversationMenu(event, conversation.id)}
                  >
                    ...
                  </button>

                  {menuOpen ? (
                    <div className="conversation-menu" role="menu" onClick={(event) => event.stopPropagation()}>
                      <button
                        type="button"
                        className="menu-button"
                        role="menuitem"
                        onClick={(event) => onStartRenameConversation(event, conversation)}
                      >
                        Rename
                      </button>
                      <button
                        type="button"
                        className="menu-button"
                        role="menuitem"
                        onClick={() => onClearConversation(conversation.id)}
                      >
                        Clear
                      </button>
                      <button
                        type="button"
                        className="menu-button danger"
                        role="menuitem"
                        onClick={() => onDeleteConversation(conversation.id)}
                      >
                        Delete
                      </button>
                    </div>
                  ) : null}
                </>
              )}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
