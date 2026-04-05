import type { KeyboardEvent as ReactKeyboardEvent, PointerEvent as ReactPointerEvent, RefObject } from "react";
import { Bars3Icon, Cog6ToothIcon, MicrophoneIcon, SpeakerWaveIcon, StopIcon } from "@heroicons/react/20/solid";
import type { ApprovalRequestToolPayload, Choice, ConversationTurn, TaskRequestToolPayload, WeatherToolPayload } from "../lib/types";
import type { ReasoningEffort } from "../lib/ui";
import type { ConnectionState, PendingVoiceReview } from "../lib/runtime";
import { ApprovalRequestCard } from "./ApprovalRequestCard";
import { TaskRequestCard } from "./TaskRequestCard";
import { VoiceTranscriptionReviewCard } from "./VoiceTranscriptionReviewCard";
import { WeatherMessageCard } from "./WeatherMessageCard";

type ChatWorkspaceProps = {
  activeConversationTitle: string;
  history: ConversationTurn[];
  messageListRef: RefObject<HTMLDivElement | null>;
  chatStatus: string;
  connectionState: ConnectionState;
  connectionSummary: string;
  lastConnectionError: string;
  replyAudioStatus: string;
  latestReplyAudioReady: boolean;
  isReplyAudioPlaying: boolean;
  chatInput: string;
  sending: boolean;
  currentListenerStatus: string;
  isListening: boolean;
  backendChoices: Choice[];
  selectedBackend: string;
  selectedModel: string;
  modelChoices: Choice[];
  reasoningEffort: ReasoningEffort;
  remoteVoiceAvailable: boolean;
  remoteVoiceBusy: boolean;
  remoteVoiceDisabledReason: string;
  remoteVoiceStatus: string;
  pendingVoiceReview: PendingVoiceReview | null;
  isRemoteRecording: boolean;
  remoteRecordingElapsedLabel: string;
  remoteVoicePressToTalk: boolean;
  speakRepliesOnThisDevice: boolean;
  onChatInputChange: (value: string) => void;
  onStartListener: () => void;
  onPauseListener: () => void;
  onShutdownListener: () => void;
  onSelectedBackendChange: (value: string) => void;
  onSelectedModelChange: (value: string) => void;
  onReasoningEffortChange: (value: ReasoningEffort) => void;
  onComposerKeyDown: (event: ReactKeyboardEvent<HTMLTextAreaElement>) => void;
  onSendMessage: () => void;
  onApprovePendingAction: () => void;
  onDenyPendingAction: () => void;
  onTrustPendingAction: () => void;
  onTrustPendingSession: () => void;
  onToggleRemoteVoice: () => void;
  onRemoteVoicePressStart: (event: ReactPointerEvent<HTMLButtonElement>) => void;
  onRemoteVoicePressEnd: (event: ReactPointerEvent<HTMLButtonElement>) => void;
  onRemoteVoicePressCancel: (event: ReactPointerEvent<HTMLButtonElement>) => void;
  onPlayLatestReplyAudio: () => void;
  onDismissVoiceReview: () => void;
  onToggleSpeakRepliesOnThisDevice: () => void;
  onReconnectHost: () => void;
  onOpenSettings: () => void;
  onOpenConversationSidebar: () => void;
  onRetryVoiceReview: () => void;
  onSendHeardVoiceReview: () => void;
  onUseSuggestedVoiceReview: () => void;
};

export function ChatWorkspace({
  activeConversationTitle,
  history,
  messageListRef,
  chatStatus,
  connectionState,
  connectionSummary,
  lastConnectionError,
  replyAudioStatus,
  latestReplyAudioReady,
  isReplyAudioPlaying,
  chatInput,
  sending,
  currentListenerStatus,
  isListening,
  backendChoices,
  selectedBackend,
  selectedModel,
  modelChoices,
  reasoningEffort,
  remoteVoiceAvailable,
  remoteVoiceBusy,
  remoteVoiceDisabledReason,
  remoteVoiceStatus,
  pendingVoiceReview,
  isRemoteRecording,
  remoteRecordingElapsedLabel,
  remoteVoicePressToTalk,
  speakRepliesOnThisDevice,
  onChatInputChange,
  onStartListener,
  onPauseListener,
  onShutdownListener,
  onSelectedBackendChange,
  onSelectedModelChange,
  onReasoningEffortChange,
  onComposerKeyDown,
  onSendMessage,
  onApprovePendingAction,
  onDenyPendingAction,
  onTrustPendingAction,
  onTrustPendingSession,
  onToggleRemoteVoice,
  onRemoteVoicePressStart,
  onRemoteVoicePressEnd,
  onRemoteVoicePressCancel,
  onPlayLatestReplyAudio,
  onDismissVoiceReview,
  onToggleSpeakRepliesOnThisDevice,
  onReconnectHost,
  onOpenSettings,
  onOpenConversationSidebar,
  onRetryVoiceReview,
  onSendHeardVoiceReview,
  onUseSuggestedVoiceReview,
}: ChatWorkspaceProps) {
  function weatherPayloadForTurn(turn: ConversationTurn): WeatherToolPayload | null {
    if (turn.tool_kind !== "weather" || !turn.tool_payload) {
      return null;
    }
    return turn.tool_payload as WeatherToolPayload;
  }

  function approvalPayloadForTurn(turn: ConversationTurn): ApprovalRequestToolPayload | null {
    if (turn.tool_kind !== "approval_request" || !turn.tool_payload) {
      return null;
    }
    return turn.tool_payload as ApprovalRequestToolPayload;
  }

  function taskPayloadForTurn(turn: ConversationTurn): TaskRequestToolPayload | null {
    if (turn.tool_kind !== "task_request" || !turn.tool_payload) {
      return null;
    }
    return turn.tool_payload as TaskRequestToolPayload;
  }

  return (
    <section className="chat-column">
      <header className="chat-header">
        <div className="chat-header-copy">
          <div className="eyebrow">Active conversation</div>
          <div className="chat-title-row">
            <button
              type="button"
              className="ghost-button icon-button mobile-nav-button"
              aria-label="Open conversations"
              title="Open conversations"
              onClick={onOpenConversationSidebar}
            >
              <Bars3Icon aria-hidden="true" />
            </button>
            <h2>{activeConversationTitle}</h2>
          </div>
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
            history.map((turn, index) => {
              const weatherPayload = weatherPayloadForTurn(turn);
              const approvalPayload = approvalPayloadForTurn(turn);
              const taskPayload = taskPayloadForTurn(turn);
              const hasToolCard = Boolean(weatherPayload || approvalPayload || taskPayload);

              return (
                <article
                  key={`${turn.role}-${index}`}
                  className={`message-row ${turn.role === "user" ? "user" : "assistant"}`}
                >
                  <div className={`message-card ${hasToolCard ? "has-tool-card" : ""}`}>
                    <div className="message-role">{turn.role === "user" ? "You" : "Jarvin"}</div>
                    <div className="message-text">{turn.message}</div>
                    {weatherPayload ? <WeatherMessageCard payload={weatherPayload} /> : null}
                    {approvalPayload ? (
                      <ApprovalRequestCard
                        payload={approvalPayload}
                        sending={sending}
                        onApprove={onApprovePendingAction}
                        onDeny={onDenyPendingAction}
                        onTrustConversation={onTrustPendingAction}
                        onTrustSession={onTrustPendingSession}
                      />
                    ) : null}
                    {taskPayload ? (
                      <TaskRequestCard
                        payload={taskPayload}
                        sending={sending}
                        onApprove={onApprovePendingAction}
                        onDeny={onDenyPendingAction}
                      />
                    ) : null}
                  </div>
                </article>
              );
            })
          )}
        </div>

        <footer className="composer-shell">
          {connectionState !== "connected" ? (
            <div className={`connection-banner connection-${connectionState}`}>
              <div className="connection-banner-copy">
                <strong>{connectionSummary}</strong>
                <span>{lastConnectionError || "The client is waiting for the Jarvin host."}</span>
              </div>
              <button type="button" className="secondary-button compact-button" onClick={onReconnectHost}>
                Reconnect
              </button>
            </div>
          ) : null}

          {pendingVoiceReview ? (
            <VoiceTranscriptionReviewCard
              review={pendingVoiceReview}
              sending={sending}
              onUseSuggestion={onUseSuggestedVoiceReview}
              onSendHeard={onSendHeardVoiceReview}
              onRetry={onRetryVoiceReview}
              onDismiss={onDismissVoiceReview}
            />
          ) : null}

          {chatStatus || remoteVoiceStatus || replyAudioStatus || latestReplyAudioReady ? (
            <div className="composer-status-row">
              {chatStatus ? <p className="composer-status">{chatStatus}</p> : null}
              {remoteVoiceStatus ? <p className="composer-status remote-voice-status">{remoteVoiceStatus}</p> : null}
              {replyAudioStatus ? <p className="composer-status reply-audio-status">{replyAudioStatus}</p> : null}
              {latestReplyAudioReady ? (
                <button
                  type="button"
                  className="ghost-button compact-button inline-status-button"
                  onClick={onPlayLatestReplyAudio}
                >
                  <SpeakerWaveIcon aria-hidden="true" />
                  {isReplyAudioPlaying ? "Stop playback" : "Play reply"}
                </button>
              ) : null}
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
                className={`ghost-button send-icon-button remote-voice-button ${isRemoteRecording ? "recording" : ""}`}
                aria-label={
                  isRemoteRecording
                    ? remoteVoicePressToTalk
                      ? "Release to send your recording"
                      : "Stop remote recording and send"
                    : remoteVoicePressToTalk
                      ? "Hold to talk from this device"
                      : "Record from this device"
                }
                title={
                  remoteVoiceAvailable
                    ? isRemoteRecording
                      ? remoteVoicePressToTalk
                        ? `Release to send (${remoteRecordingElapsedLabel})`
                        : `Stop recording and send (${remoteRecordingElapsedLabel})`
                      : remoteVoicePressToTalk
                        ? "Hold to talk from this device"
                        : "Record from this device"
                    : remoteVoiceDisabledReason
                }
                onClick={onToggleRemoteVoice}
                onPointerDown={onRemoteVoicePressStart}
                onPointerUp={onRemoteVoicePressEnd}
                onPointerCancel={onRemoteVoicePressCancel}
                disabled={!remoteVoiceAvailable || remoteVoiceBusy || sending}
              >
                {isRemoteRecording ? <StopIcon aria-hidden="true" /> : <MicrophoneIcon aria-hidden="true" />}
              </button>

              <button
                type="button"
                className={`ghost-button send-icon-button reply-audio-toggle-button ${speakRepliesOnThisDevice ? "active" : ""}`}
                aria-label={speakRepliesOnThisDevice ? "Disable spoken replies on this device" : "Enable spoken replies on this device"}
                title={speakRepliesOnThisDevice ? "Spoken replies are enabled on this device" : "Enable spoken replies on this device"}
                onClick={onToggleSpeakRepliesOnThisDevice}
              >
                <SpeakerWaveIcon aria-hidden="true" />
              </button>

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
