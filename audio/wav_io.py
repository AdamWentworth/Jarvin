# audio/wav_io.py
from __future__ import annotations

import wave
import numpy as np
import os

def linear_resample(audio: np.ndarray, src_hz: int, dst_hz: int) -> np.ndarray:
    if src_hz == dst_hz or audio.size == 0:
        return audio.astype(np.float32, copy=False)
    ratio = float(dst_hz) / float(src_hz)
    n = int(round(len(audio) * ratio))
    xp = np.linspace(0.0, 1.0, num=len(audio), endpoint=False, dtype=np.float64)
    fp = audio.astype(np.float64, copy=False)
    x_new = np.linspace(0.0, 1.0, num=n, endpoint=False, dtype=np.float64)
    y = np.interp(x_new, xp, fp).astype(np.float32, copy=False)
    return y


def wav_to_float32_mono_16k(path: str) -> np.ndarray:
    with wave.open(path, "rb") as wf:
        nch = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        fr = wf.getframerate()
        nframes = wf.getnframes()
        audio_bytes = wf.readframes(nframes)

    if sampwidth != 2:
        raise ValueError(f"Expected 16-bit PCM; got sampwidth={sampwidth}")

    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    if nch == 2:
        audio = audio.reshape(-1, 2).mean(axis=1).astype(np.float32, copy=False)

    if fr != 16000:
        audio = linear_resample(audio, src_hz=fr, dst_hz=16000)

    return audio

def _peak_normalize_int16(x: np.ndarray, target_dbfs: float) -> np.ndarray:
    if x.size == 0:
        return x
    peak = int(np.max(np.abs(x)))
    if peak == 0:
        return x
    target_linear = 32767.0 * (10.0 ** (target_dbfs / 20.0))
    gain = target_linear / float(peak)
    return np.clip(x.astype(np.float32) * gain, -32768.0, 32767.0).astype(np.int16)

def write_wav_int16_mono(path: str, pcm: np.ndarray, sample_rate: int, normalize_dbfs: float | None = None) -> None:
    y = _peak_normalize_int16(pcm, normalize_dbfs) if normalize_dbfs is not None else pcm
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(y.tobytes())
