# backend/asr/whisper.py
from __future__ import annotations

from typing import Optional
from functools import lru_cache
import wave

import numpy as np
import whisper
import torch
import torch.nn as nn

import config as cfg
from audio.wav_io import pcm_to_float32_mono_16k, wav_to_float32_mono_16k


def _best_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    try:
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def _force_layernorm_fp32(model: nn.Module) -> None:
    """
    Fix mixed-precision LayerNorm issues on some torch/CUDA builds:
    Whisper's LayerNorm forward does x.float() but if weights are fp16,
    torch.layer_norm can error: expected Float but found Half.

    Solution: keep LayerNorm params in fp32 even when the model is fp16.
    """
    for m in model.modules():
        if isinstance(m, nn.LayerNorm):
            m.float()


def _infer_fp16_flag(model: whisper.Whisper, device: str) -> bool:
    """
    Whisper's transcribe(fp16=...) should match the model's actual dtype.
    """
    if device != "cuda":
        return False
    try:
        p = next(model.parameters())
        return p.dtype == torch.float16
    except Exception:
        return False


@lru_cache(maxsize=8)
def _get_model_and_device(model_size: Optional[str]) -> tuple[whisper.Whisper, str]:
    """
    Cache Whisper model per `model_size`. Changing size in config will be honored
    without restarting Python if a different `model_size` is requested.
    """
    device = _best_device()
    size = (model_size or cfg.settings.whisper_model_size or "small").strip().lower()

    model = whisper.load_model(size, device=device)

    # Prefer fp16 on CUDA for speed, but keep LayerNorm in fp32 to avoid
    # RuntimeError: expected scalar type Float but found Half
    if device == "cuda":
        try:
            model.half()
            _force_layernorm_fp32(model)
        except Exception:
            # Non-fatal: run in fp32 instead
            try:
                model.float()
            except Exception:
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


def _load_audio_waveform(file_path: str) -> np.ndarray:
    """
    Load local audio into Whisper's expected mono 16 kHz float32 waveform.

    Fast-path RIFF/WAV utterances without ffmpeg, but fall back to Whisper's
    broader container decoder for uploads such as webm/opus from mobile clients.
    """
    try:
        return wav_to_float32_mono_16k(file_path)
    except (wave.Error, EOFError, ValueError):
        return whisper.load_audio(file_path)


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
    waveform: np.ndarray = _load_audio_waveform(file_path)

    fp16 = _infer_fp16_flag(model, device)
    kwargs = {"fp16": fp16}

    # Inference-mode for speed + lower overhead
    with torch.inference_mode():
        result = model.transcribe(waveform, language="en", **kwargs)

    return result.get("text", "")


def transcribe_pcm(
    pcm: np.ndarray,
    sample_rate: int,
    *,
    model: Optional[whisper.Whisper] = None,
    device: Optional[str] = None,
    model_size: Optional[str] = None,
    normalize_dbfs: Optional[float] = None,
) -> str:
    """
    Transcribe in-memory PCM without a temporary WAV round-trip.
    """
    model, device = _ensure_model_and_device(model, device, model_size)
    waveform: np.ndarray = pcm_to_float32_mono_16k(
        pcm,
        sample_rate,
        normalize_dbfs=normalize_dbfs,
    )

    fp16 = _infer_fp16_flag(model, device)
    kwargs = {"fp16": fp16}

    # Inference-mode for speed + lower overhead
    with torch.inference_mode():
        result = model.transcribe(waveform, language="en", **kwargs)

    return result.get("text", "")


class WhisperASR:
    """Implements ASRTranscriber using a cached Whisper model/device per size."""
    def __init__(self, model_size: Optional[str] = None) -> None:
        self.model, self.device = _get_model_and_device(model_size)

    def transcribe(self, wav_path: str) -> str:
        return transcribe_audio(wav_path, model=self.model, device=self.device)

    def transcribe_pcm(self, pcm: np.ndarray, sample_rate: int, normalize_dbfs: Optional[float] = None) -> str:
        return transcribe_pcm(
            pcm,
            sample_rate,
            model=self.model,
            device=self.device,
            normalize_dbfs=normalize_dbfs,
        )
