# backend/core/ports.py
from __future__ import annotations
from typing import Protocol, Optional
import numpy as np

class ASRTranscriber(Protocol):
    def transcribe(self, wav_path: str) -> str: ...

class LLMChatEngine(Protocol):
    def reply(self, user_text: str) -> str: ...

class AudioSink(Protocol):
    def write_wav(self, path: str, pcm: np.ndarray, sample_rate: int,
                  normalize_dbfs: Optional[float]) -> None: ...
