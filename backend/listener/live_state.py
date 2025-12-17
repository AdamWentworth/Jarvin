# backend/listener/live_state.py
from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

# Lock + condition for coordinating UI waiters and backend updates
_lock = threading.Lock()
_cv = threading.Condition(_lock)

# Monotonic sequence number that advances once per utterance/cycle snapshot.
_seq: int = 0

_state: Dict[str, Any] = {
    "ts": None,          # last update timestamp (monotonic)
    "seq": None,         # last utterance sequence id (int), advances in set_snapshot()
    "utter_ms": None,    # duration of the utterance audio
    "transcript": None,  # ASR text
    "reply": None,       # LLM reply text
    "cycle_ms": None,    # end-to-end processing time for the cycle
    "wav_path": None,    # last utterance wav file path (temp)
    "tts_url": None,     # relative URL to synthesized speech (served via /_temp)
    "recording": False,  # VAD is currently capturing speech
    "processing": False, # backend is currently processing an utterance
}


def set_snapshot(
    *,
    transcript: Optional[str],
    reply: Optional[str],
    cycle_ms: Optional[int],
    utter_ms: Optional[int],
    wav_path: Optional[str],
    tts_url: Optional[str],
) -> None:
    """
    Called once per completed utterance/cycle. Bumps the global seq so the UI
    can detect a *new* result and update transcript/reply/metrics exactly once.
    """
    global _seq
    with _cv:
        _seq += 1
        _state.update({
            "ts": time.monotonic(),
            "seq": _seq,
            "transcript": transcript,
            "reply": reply,
            "cycle_ms": cycle_ms,
            "utter_ms": utter_ms,
            "wav_path": wav_path,
            "tts_url": tts_url,
        })
        _cv.notify_all()  # wake any UI streams waiting for a new utterance


def set_status(
    *,
    recording: Optional[bool] = None,
    processing: Optional[bool] = None
) -> None:
    """
    Updates 'recording'/'processing' flags. Does NOT bump seq (so UI won’t treat
    it as a new utterance), but we still notify waiters so a UI stream/poller
    can reflect banner changes immediately.
    """
    if recording is None and processing is None:
        return

    with _cv:
        if recording is not None:
            _state["recording"] = bool(recording)
        if processing is not None:
            _state["processing"] = bool(processing)
        _state["ts"] = time.monotonic()
        _cv.notify_all()  # wake anyone interested in status flips


def get_snapshot() -> Dict[str, Any]:
    """Return a shallow copy of current state."""
    with _lock:
        return dict(_state)


def wait_next(since: Optional[int], timeout: Optional[float] = None) -> Dict[str, Any]:
    """
    Block until either:
      - _seq > since  (new utterance), or
      - a status flip happens (recording/processing), or
      - timeout elapses.

    Returns the current snapshot (copy). If timeout elapses, returns latest state.
    """
    deadline = None if timeout is None else (time.monotonic() + max(0.0, timeout))
    with _cv:
        while True:
            cur_seq = _state.get("seq")
            if isinstance(cur_seq, int) and (since is None or cur_seq > since):
                return dict(_state)

            remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
            if remaining == 0.0:
                return dict(_state)
            _cv.wait(timeout=remaining)
            # loop back and re-check
