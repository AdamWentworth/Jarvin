# backend/asr/whisper.py
from __future__ import annotations
from typing import Optional, Tuple
from functools import lru_cache

import numpy as np
import whisper
import torch

import config as cfg
from audio.wav_io import wav_to_float32_mono_16k


def _best_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    try:
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


@lru_cache(maxsize=8)
def _get_model_and_device(model_size: Optional[str]) -> tuple[whisper.Whisper, str]:
    """
    Cache Whisper model per `model_size`. Changing size in config will now be honored
    without restarting Python if a different `model_size` is requested.
    """
    device = _best_device()
    size = (model_size or cfg.settings.whisper_model_size or "small").strip().lower()

    model = whisper.load_model(size, device=device)
    # fp16 only on CUDA; MPS/CPU stay in fp32 for stability
    if device == "cuda":
        try:
            model.half()
        except Exception:
            # Non-fatal: run in fp32 instead
            pass
    return model, device


def _ensure_model_and_device(
    model: Optional[whisper.Whisper],
    device: Optional[str],
    model_size: Optional[str],
) -> tuple[whisper.Whisper, str]:
    if model is not None and device is not None:
        return model, device
    return _get_model_and_device(model_size)


def transcribe_audio(
    file_path: str,
    *,
    model: Optional[whisper.Whisper] = None,
    device: Optional[str] = None,
    model_size: Optional[str] = None,
) -> str:
    """
    Transcribe an audio file using Whisper. Resamples to 16 kHz mono float32.
    """
    model, device = _ensure_model_and_device(model, device, model_size)
    waveform: np.ndarray = wav_to_float32_mono_16k(file_path)
    # fp16 True only on CUDA
    kwargs = {"fp16": device == "cuda"}
    result = model.transcribe(waveform, language="en", **kwargs)
    return result.get("text", "")


class WhisperASR:
    """Implements ASRTranscriber using a cached Whisper model/device per size."""
    def __init__(self, model_size: Optional[str] = None) -> None:
        self.model, self.device = _get_model_and_device(model_size)

    def transcribe(self, wav_path: str) -> str:
        return transcribe_audio(wav_path, model=self.model, device=self.device)
