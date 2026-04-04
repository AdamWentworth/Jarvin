import type { KeyboardEvent as ReactKeyboardEvent, RefObject } from "react";
import { Cog6ToothIcon } from "@heroicons/react/20/solid";
import type { Choice, ConversationTurn } from "../lib/types";
import type { ReasoningEffort } from "../lib/ui";

type ChatWorkspaceProps = {
  activeConversationTitle: string;
  history: ConversationTurn[];
  messageListRef: RefObject<HTMLDivElement | null>;
  chatStatus: string;
  chatInput: string;
  sending: boolean;
  currentListenerStatus: string;
  isListening: boolean;
  backendChoices: Choice[];
  selectedBackend: string;
  selectedModel: string;
  modelChoices: Choice[];
  reasoningEffort: ReasoningEffort;
  onChatInputChange: (value: string) => void;
  onStartListener: () => void;
  onPauseListener: () => void;
  onShutdownListener: () => void;
  onSelectedBackendChange: (value: string) => void;
  onSelectedModelChange: (value: string) => void;
  onReasoningEffortChange: (value: ReasoningEffort) => void;
  onComposerKeyDown: (event: ReactKeyboardEvent<HTMLTextAreaElement>) => void;
  onSendMessage: () => void;
  onOpenSettings: () => void;
};

export function ChatWorkspace({
  activeConversationTitle,
  history,
  messageListRef,
  chatStatus,
  chatInput,
  sending,
  currentListenerStatus,
  isListening,
  backendChoices,
  selectedBackend,
  selectedModel,
  modelChoices,
  reasoningEffort,
  onChatInputChange,
  onStartListener,
  onPauseListener,
  onShutdownListener,
  onSelectedBackendChange,
  onSelectedModelChange,
  onReasoningEffortChange,
  onComposerKeyDown,
  onSendMessage,
  onOpenSettings,
}: ChatWorkspaceProps) {
  return (
    <section className="chat-column">
      <header className="chat-header">
        <div className="chat-header-copy">
          <div className="eyebrow">Active conversation</div>
          <h2>{activeConversationTitle}</h2>
        </div>

        <div className="listener-controls">
          <button
            type="button"
            className={`listener-state-button ${isListening ? `status-${currentListenerStatus.toLowerCase()}` : "status-stopped"}`}
            onClick={isListening ? undefined : onStartListener}
            disabled={isListening}
          >
            {isListening ? currentListenerStatus : "Start"}
          </button>

          <button type="button" className="pause-button header-action-button" onClick={onPauseListener} disabled={!isListening}>
            Pause
          </button>

          <button type="button" className="danger-button header-action-button" onClick={onShutdownListener}>
            Shutdown
          </button>
        </div>

        <button
          type="button"
          className="ghost-button icon-button chat-settings-button"
          aria-label="Open settings"
          title="Settings"
          onClick={onOpenSettings}
        >
          <Cog6ToothIcon aria-hidden="true" />
        </button>
      </header>

      <section className="chat-shell">
        <div className="message-list" ref={messageListRef}>
          {history.length === 0 ? (
            <div className="empty-state">
              <h3>Ready for typed chat</h3>
              <p>Start a conversation here while the host keeps the models and GPU local.</p>
            </div>
          ) : (
            history.map((turn, index) => (
              <article
                key={`${turn.role}-${index}`}
                className={`message-row ${turn.role === "user" ? "user" : "assistant"}`}
              >
                <div className="message-card">
                  <div className="message-role">{turn.role === "user" ? "You" : "Jarvin"}</div>
                  <div className="message-text">{turn.message}</div>
                </div>
              </article>
            ))
          )}
        </div>

        <footer className="composer-shell">
          {chatStatus ? (
            <div className="composer-status-row">
              <p className="composer-status">{chatStatus}</p>
            </div>
          ) : null}

          <textarea
            value={chatInput}
            onChange={(event) => onChatInputChange(event.currentTarget.value)}
            onKeyDown={onComposerKeyDown}
            placeholder="Message Jarvin. Press Enter to send, Shift+Enter for a new line."
          />

          <div className="composer-toolbar">
            <div className="composer-controls">
              <div className="composer-control composer-select-shell">
                <select
                  aria-label="Backend"
                  title="Backend"
                  value={selectedBackend}
                  onChange={(event) => onSelectedBackendChange(event.currentTarget.value)}
                >
                  {backendChoices.map((choice) => (
                    <option key={choice.value} value={choice.value}>
                      {choice.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="composer-control composer-select-shell composer-model-shell">
                <select
                  aria-label="Model"
                  title="Model"
                  value={selectedModel}
                  onChange={(event) => onSelectedModelChange(event.currentTarget.value)}
                >
                  {modelChoices.map((choice) => (
                    <option key={choice.value} value={choice.value}>
                      {choice.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="composer-control composer-select-shell">
                <select
                  aria-label="Reasoning effort"
                  title="Reasoning effort"
                  value={reasoningEffort}
                  onChange={(event) => onReasoningEffortChange(event.currentTarget.value as ReasoningEffort)}
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="extra_high">Extra High</option>
                </select>
              </div>
            </div>

            <div className="composer-buttons">
              <button
                type="button"
                className="primary-button send-button send-icon-button"
                aria-label={sending ? "Sending message" : "Send message"}
                title={sending ? "Sending..." : "Send message"}
                onClick={onSendMessage}
                disabled={sending || !chatInput.trim()}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    d="M12 19V5"
                    fill="none"
                    stroke="currentColor"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                  />
                  <path
                    d="M7.5 9.5L12 5L16.5 9.5"
                    fill="none"
                    stroke="currentColor"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                  />
                </svg>
              </button>
            </div>
          </div>
        </footer>
      </section>
    </section>
  );
}
