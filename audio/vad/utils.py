# audio/vad/utils.py
from __future__ import annotations

import sys
from typing import Optional

import numpy as np

import config as cfg
from audio.wav_io import write_wav_int16_mono as _write_wav_int16_mono

def rms_int16(x: np.ndarray) -> float:
    if x.size == 0:
        return 0.0
    y = x.astype(np.float32)
    return float(np.sqrt(np.mean(y * y)))


def _isatty(stream) -> bool:
    try:
        return stream.isatty()
    except Exception:
        return False


class TTYStatus:
    """Minimal TTY status line helper; disabled if not a TTY or cfg disables it."""
    def __init__(self) -> None:
        s = cfg.settings
        self.enabled = s.vad_tty_status and _isatty(sys.stderr)
        self._last_str = ""

    def update(self, s: str) -> None:
        if not self.enabled or s == self._last_str:
            return
        sys.stderr.write("\r" + s + "\x1b[K")
        sys.stderr.flush()
        self._last_str = s

    def clear(self) -> None:
        if not self.enabled:
            return
        sys.stderr.write("\r\x1b[K")
        sys.stderr.flush()
        self._last_str = ""


def clamp_floor(x: float) -> float:
    s = cfg.settings
    return max(s.vad_floor_min, min(s.vad_floor_max, x))


def ema(value: float, prev: float, alpha: float) -> float:
    return (alpha * prev) + ((1.0 - alpha) * value)


def threshold(floor_rms: float) -> float:
    s = cfg.settings
    return max(s.vad_threshold_abs, floor_rms * s.vad_threshold_mult)


def write_wav(path: str, pcm: np.ndarray, sample_rate: int, normalize_dbfs: Optional[float]) -> None:
    _write_wav_int16_mono(path, pcm, sample_rate, normalize_dbfs)
