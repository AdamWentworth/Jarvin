# backend/tts/engine.py
from __future__ import annotations

import os
import threading
import pyttsx3

from backend.util.paths import temp_unique_path

# Single shared engine guarded by a lock so requests don't overlap.
_engine_lock = threading.Lock()
_engine = None  # type: pyttsx3.Engine | None


def _get_engine() -> "pyttsx3.Engine":
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = pyttsx3.init()
            # Optional voice tuning:
            # _engine.setProperty("rate", 180)
            # _engine.setProperty("volume", 1.0)
        return _engine


def synth_to_wav(text: str) -> str:
    """
    Synthesize `text` to a WAV file in the temp directory and return its absolute path.
    Blocking; safe to call from a worker thread.
    """
    if not text or not text.strip():
        raise ValueError("TTS received empty text.")

    out_path = temp_unique_path(prefix="tts_", suffix=".wav")
    eng = _get_engine()

    with _engine_lock:
        eng.save_to_file(text, out_path)
        eng.runAndWait()

    # Validate output exists and is non-empty
    if not os.path.exists(out_path) or os.path.getsize(out_path) <= 0:
        raise RuntimeError("TTS engine produced no audio output.")

    return out_path
