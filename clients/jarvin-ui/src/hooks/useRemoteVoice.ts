import { PointerEvent as ReactPointerEvent, useEffect, useMemo, useRef, useState } from "react";

import { buildApiUrl } from "../lib/api";
import {
  DEFAULT_REMOTE_VOICE_DIAGNOSTICS,
  detectMobileClient,
  detectRemoteVoiceCapability,
  finalizeRemoteRecording,
  formatDuration,
  getStoredSpeakRepliesPreference,
  REMOTE_RECORDING_LIMIT_SECONDS,
  setStoredSpeakRepliesPreference,
  stopRemoteStream,
  type PendingVoiceReview,
  type RemoteVoiceDiagnostics,
  type SendSource,
  withRecorderStop,
} from "../lib/runtime";

type UseRemoteVoiceOptions = {
  describeError: (error: unknown) => string;
  onSendMessage: (text: string, source: SendSource) => Promise<void>;
};

export function useRemoteVoice({ describeError, onSendMessage }: UseRemoteVoiceOptions) {
  const [replyAudioStatus, setReplyAudioStatus] = useState("");
  const [latestReplyAudioUrl, setLatestReplyAudioUrl] = useState<string | null>(null);
  const [isReplyAudioPlaying, setIsReplyAudioPlaying] = useState(false);
  const [speakRepliesOnThisDevice, setSpeakRepliesOnThisDevice] = useState<boolean>(() => getStoredSpeakRepliesPreference());
  const [remoteVoiceStatus, setRemoteVoiceStatus] = useState("");
  const [remoteVoiceDiagnostics, setRemoteVoiceDiagnostics] = useState<RemoteVoiceDiagnostics>(DEFAULT_REMOTE_VOICE_DIAGNOSTICS);
  const [isRemoteRecording, setIsRemoteRecording] = useState(false);
  const [isRemoteTranscribing, setIsRemoteTranscribing] = useState(false);
  const [remoteRecordingSeconds, setRemoteRecordingSeconds] = useState(0);
  const [pendingVoiceReview, setPendingVoiceReview] = useState<PendingVoiceReview | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const mediaChunksRef = useRef<Blob[]>([]);
  const replyAudioRef = useRef<HTMLAudioElement | null>(null);
  const remoteRecordingStartedAtRef = useRef<number | null>(null);
  const remoteRecordingTimerRef = useRef<number | null>(null);
  const suppressRemoteVoiceClickRef = useRef(false);

  const remoteVoiceCapability = useMemo(
    () => detectRemoteVoiceCapability(),
    [],
  );

  const remoteVoicePressToTalk = useMemo(
    () => detectMobileClient(),
    [],
  );

  const remoteRecordingElapsedLabel = useMemo(
    () => formatDuration(remoteRecordingSeconds),
    [remoteRecordingSeconds],
  );

  useEffect(() => {
    return () => {
      clearRemoteRecordingTimer();
      const recorder = mediaRecorderRef.current;
      if (recorder && recorder.state !== "inactive") {
        recorder.onstop = null;
        withRecorderStop(recorder);
      }
      stopRemoteStream(mediaStreamRef);
      const replyAudio = replyAudioRef.current;
      if (replyAudio) {
        replyAudio.pause();
        replyAudioRef.current = null;
      }
    };
  }, []);

  function setRemoteVoiceStage<K extends keyof RemoteVoiceDiagnostics>(
    key: K,
    value: RemoteVoiceDiagnostics[K],
  ) {
    setRemoteVoiceDiagnostics((current) => ({ ...current, [key]: value }));
  }

  function resetRemoteVoiceDiagnostics(note = "") {
    setRemoteVoiceDiagnostics({ ...DEFAULT_REMOTE_VOICE_DIAGNOSTICS, note });
  }

  function clearRemoteRecordingTimer() {
    if (remoteRecordingTimerRef.current !== null) {
      window.clearInterval(remoteRecordingTimerRef.current);
      remoteRecordingTimerRef.current = null;
    }
    remoteRecordingStartedAtRef.current = null;
    setRemoteRecordingSeconds(0);
  }

  function updateRemoteRecordingStatus(seconds: number) {
    const duration = formatDuration(seconds);
    setRemoteVoiceStatus(
      remoteVoicePressToTalk
        ? `Listening on this device. Release to send (${duration}).`
        : `Listening on this device. Tap again to send (${duration}).`,
    );
  }

  async function playReplyAudio(url: string) {
    const absoluteUrl = buildApiUrl(url);
    const currentAudio = replyAudioRef.current;
    if (currentAudio) {
      currentAudio.pause();
      currentAudio.currentTime = 0;
    }

    const audio = new Audio(absoluteUrl);
    audio.preload = "auto";
    replyAudioRef.current = audio;

    audio.onended = () => {
      setIsReplyAudioPlaying(false);
      setReplyAudioStatus("");
      setRemoteVoiceStage("playback", "done");
    };

    audio.onerror = () => {
      setIsReplyAudioPlaying(false);
      setReplyAudioStatus("Reply audio could not be played on this device.");
      setRemoteVoiceStage("playback", "error");
    };

    try {
      setIsReplyAudioPlaying(true);
      setReplyAudioStatus("Playing Jarvin's reply...");
      setRemoteVoiceStage("playback", "working");
      await audio.play();
    } catch (error) {
      setIsReplyAudioPlaying(false);
      setReplyAudioStatus(describeError(error) || "Reply audio is ready. Tap play to hear it.");
      setRemoteVoiceStage("playback", "error");
      throw error;
    }
  }

  function stopReplyAudio(options?: { quiet?: boolean }) {
    const audio = replyAudioRef.current;
    if (!audio) {
      return;
    }
    audio.pause();
    audio.currentTime = 0;
    setIsReplyAudioPlaying(false);
    setReplyAudioStatus(options?.quiet ? "" : "Reply playback stopped.");
    setRemoteVoiceStage("playback", "idle");
  }

  function handleToggleSpeakRepliesOnThisDevice() {
    setSpeakRepliesOnThisDevice((current) => {
      const next = !current;
      setStoredSpeakRepliesPreference(next);
      if (!next) {
        stopReplyAudio({ quiet: true });
      }
      setReplyAudioStatus(next ? "Jarvin will speak replies on this device when audio is available." : "");
      return next;
    });
  }

  async function handlePlayLatestReplyAudio() {
    if (isReplyAudioPlaying) {
      stopReplyAudio();
      return;
    }

    if (!latestReplyAudioUrl) {
      setReplyAudioStatus("No reply audio is ready yet.");
      return;
    }

    try {
      await playReplyAudio(latestReplyAudioUrl);
    } catch {
      // Status is already updated inside playReplyAudio.
    }
  }

  async function beginRemoteRecording() {
    if (!remoteVoiceCapability.available) {
      setRemoteVoiceStatus(remoteVoiceCapability.reason);
      return;
    }

    if (isRemoteTranscribing) {
      return;
    }

    const activeRecorder = mediaRecorderRef.current;
    if (activeRecorder && activeRecorder.state !== "inactive") {
      return;
    }

    try {
      stopReplyAudio({ quiet: true });
      setPendingVoiceReview(null);

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaStreamRef.current = stream;
      mediaRecorderRef.current = recorder;
      mediaChunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          mediaChunksRef.current.push(event.data);
        }
      };

      recorder.onerror = () => {
        clearRemoteRecordingTimer();
        setRemoteVoiceStatus("Remote microphone capture failed.");
        setIsRemoteRecording(false);
        mediaRecorderRef.current = null;
        mediaChunksRef.current = [];
        setPendingVoiceReview(null);
        stopRemoteStream(mediaStreamRef);
      };

      recorder.onstop = () => {
        clearRemoteRecordingTimer();
        void finalizeRemoteRecording({
          mediaChunksRef,
          mediaRecorderRef,
          mediaStreamRef,
          setIsRemoteRecording,
          setIsRemoteTranscribing,
          setRemoteVoiceStatus,
          setRemoteVoiceDiagnostics,
          setPendingVoiceReview,
          sendMessage: (text) => onSendMessage(text, "remote_voice"),
        });
      };

      resetRemoteVoiceDiagnostics("Listening for speech on this device.");
      setRemoteVoiceStage("microphone", "working");
      remoteRecordingStartedAtRef.current = Date.now();
      setRemoteRecordingSeconds(0);
      recorder.start();
      setIsRemoteRecording(true);
      updateRemoteRecordingStatus(0);
      remoteRecordingTimerRef.current = window.setInterval(() => {
        const startedAt = remoteRecordingStartedAtRef.current;
        if (!startedAt) {
          return;
        }

        const elapsedSeconds = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
        setRemoteRecordingSeconds(elapsedSeconds);

        if (elapsedSeconds >= REMOTE_RECORDING_LIMIT_SECONDS) {
          clearRemoteRecordingTimer();
          setRemoteVoiceStatus("Maximum recording length reached. Sending now...");
          const currentRecorder = mediaRecorderRef.current;
          if (currentRecorder && currentRecorder.state !== "inactive") {
            withRecorderStop(currentRecorder);
          }
          return;
        }

        updateRemoteRecordingStatus(elapsedSeconds);
      }, 1000);

      if ("vibrate" in navigator) {
        try {
          navigator.vibrate(10);
        } catch {
          // Ignore vibration failures on unsupported shells.
        }
      }
    } catch (error) {
      clearRemoteRecordingTimer();
      setRemoteVoiceStage("microphone", "error");
      setRemoteVoiceDiagnostics((current) => ({ ...current, note: describeError(error) }));
      setRemoteVoiceStatus(describeError(error) || "Microphone permission was denied.");
    }
  }

  async function handleSendReviewedVoiceTranscript(mode: "suggested" | "heard") {
    if (!pendingVoiceReview) {
      return;
    }

    const selectedText =
      mode === "suggested" && pendingVoiceReview.review.suggested_text
        ? pendingVoiceReview.review.suggested_text
        : pendingVoiceReview.heardText;
    const reviewSnapshot = pendingVoiceReview;
    setPendingVoiceReview(null);
    setRemoteVoiceStatus(`Sending: ${selectedText}`);
    setRemoteVoiceDiagnostics((current) => ({
      ...current,
      chat: "working",
      note: "Sending the reviewed voice transcript to the Jarvin host.",
    }));

    try {
      await onSendMessage(selectedText, "remote_voice");
    } catch (error) {
      setPendingVoiceReview(reviewSnapshot);
      setRemoteVoiceDiagnostics((current) => ({
        ...current,
        chat: "error",
        note: describeError(error),
      }));
      setRemoteVoiceStatus(describeError(error) || "Could not send the reviewed voice transcript.");
    }
  }

  async function handleRetryPendingVoiceReview() {
    setPendingVoiceReview(null);
    setRemoteVoiceStatus("Okay, try saying that again.");
    setRemoteVoiceDiagnostics((current) => ({
      ...current,
      chat: "idle",
      note: "Voice review dismissed. Ready to listen again.",
    }));
    await beginRemoteRecording();
  }

  function handleDismissPendingVoiceReview() {
    setPendingVoiceReview(null);
    setRemoteVoiceStatus("Voice review dismissed. Nothing was sent.");
    setRemoteVoiceDiagnostics((current) => ({
      ...current,
      chat: "idle",
      note: "Voice review dismissed. Nothing was sent to Jarvin.",
    }));
  }

  function finishRemoteRecording() {
    const activeRecorder = mediaRecorderRef.current;
    if (!activeRecorder || activeRecorder.state === "inactive") {
      return;
    }

    clearRemoteRecordingTimer();
    setRemoteVoiceStatus("Finishing remote capture...");
    withRecorderStop(activeRecorder);

    if ("vibrate" in navigator) {
      try {
        navigator.vibrate(12);
      } catch {
        // Ignore vibration failures on unsupported shells.
      }
    }
  }

  async function handleRemoteVoiceToggle() {
    if (remoteVoicePressToTalk && suppressRemoteVoiceClickRef.current) {
      suppressRemoteVoiceClickRef.current = false;
      return;
    }

    if (isRemoteRecording) {
      finishRemoteRecording();
      return;
    }

    await beginRemoteRecording();
  }

  function handleRemoteVoicePressStart(event: ReactPointerEvent<HTMLButtonElement>) {
    if (!remoteVoicePressToTalk || !remoteVoiceCapability.available || isRemoteTranscribing) {
      return;
    }

    suppressRemoteVoiceClickRef.current = true;
    event.preventDefault();

    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch {
      // Pointer capture is best-effort for keeping release events together.
    }

    if (!isRemoteRecording) {
      void beginRemoteRecording();
    }
  }

  function handleRemoteVoicePressEnd(event: ReactPointerEvent<HTMLButtonElement>) {
    if (!remoteVoicePressToTalk) {
      return;
    }

    try {
      if (event.currentTarget.hasPointerCapture(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId);
      }
    } catch {
      // Ignore capture release issues.
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      finishRemoteRecording();
    }
  }

  function handleRemoteVoicePressCancel(event: ReactPointerEvent<HTMLButtonElement>) {
    if (!remoteVoicePressToTalk) {
      return;
    }

    try {
      if (event.currentTarget.hasPointerCapture(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId);
      }
    } catch {
      // Ignore capture release issues.
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      finishRemoteRecording();
    }

    suppressRemoteVoiceClickRef.current = false;
  }

  return {
    beginRemoteRecording,
    handleDismissPendingVoiceReview,
    handlePlayLatestReplyAudio,
    handleRemoteVoicePressCancel,
    handleRemoteVoicePressEnd,
    handleRemoteVoicePressStart,
    handleRetryPendingVoiceReview,
    handleSendReviewedVoiceTranscript,
    handleRemoteVoiceToggle,
    handleToggleSpeakRepliesOnThisDevice,
    isRemoteRecording,
    isRemoteTranscribing,
    isReplyAudioPlaying,
    latestReplyAudioUrl,
    pendingVoiceReview,
    playReplyAudio,
    remoteRecordingElapsedLabel,
    remoteVoiceCapability,
    remoteVoiceDiagnostics,
    remoteVoicePressToTalk,
    remoteVoiceStatus,
    replyAudioStatus,
    resetRemoteVoiceDiagnostics,
    setLatestReplyAudioUrl,
    setReplyAudioStatus,
    setRemoteVoiceDiagnostics,
    setRemoteVoiceStage,
    speakRepliesOnThisDevice,
    stopReplyAudio,
  };
}
