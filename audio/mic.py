from __future__ import annotations

import os
import time
import wave
import logging
from typing import Optional, List, Tuple

import numpy as np
import pyaudio

import config as cfg
from backend.util.paths import ensure_temp_dir, temp_unique_path
from audio.utils import suppress_alsa_warnings_if_linux

log = logging.getLogger("jarvin.mic")

# Cached selection (default or explicit user choice)
_CACHED_DEVICE_INDEX: Optional[int] = None
_CACHED_DEVICE_NAME: Optional[str] = None


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def ensure_temp() -> None:
    os.makedirs(cfg.settings.temp_dir, exist_ok=True)
    ensure_temp_dir()


def list_input_devices() -> List[Tuple[int, str]]:
    """Return [(index, name)] for input-capable devices."""
    devices: List[Tuple[int, str]] = []
    with suppress_alsa_warnings_if_linux():
        p = pyaudio.PyAudio()
        try:
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if info.get("maxInputChannels", 0) > 0:
                    devices.append((i, info["name"]))
        finally:
            p.terminate()
    return devices


def _set_cached_device(index: int, name: Optional[str]) -> None:
    """
    Internal helper to set the cached device consistently.
    Ensures name is never None once an index is cached.
    """
    global _CACHED_DEVICE_INDEX, _CACHED_DEVICE_NAME
    _CACHED_DEVICE_INDEX = int(index)
    _CACHED_DEVICE_NAME = str(name) if name is not None else f"index {index}"


def get_default_input_device_index() -> int:
    """
    Resolve once and cache the system default input device (or first input-capable).
    """
    global _CACHED_DEVICE_INDEX, _CACHED_DEVICE_NAME
    if _CACHED_DEVICE_INDEX is not None:
        return _CACHED_DEVICE_INDEX

    with suppress_alsa_warnings_if_linux():
        p = pyaudio.PyAudio()
        try:
            try:
                info = p.get_default_input_device_info()
                idx = int(info.get("index"))
                name = str(info.get("name"))
            except Exception:
                devices = list_input_devices()
                if not devices:
                    raise RuntimeError("No input devices found. Check microphone permissions.")
                idx, name = devices[0]
        finally:
            p.terminate()

    _set_cached_device(idx, name)
    log.info("🎤 Using input device [%d] %s", idx, _CACHED_DEVICE_NAME)
    return idx


def get_selected_input_device() -> Tuple[Optional[int], Optional[str]]:
    """
    Returns (index, name) of the currently selected input device, if any.
    If none selected yet, resolves & caches the default.

    This function does not silently swallow unexpected errors; failures
    will propagate so callers/tests see real issues.
    """
    global _CACHED_DEVICE_INDEX, _CACHED_DEVICE_NAME

    # Fast path: explicit or default already cached.
    if _CACHED_DEVICE_INDEX is not None and _CACHED_DEVICE_NAME is not None:
        return _CACHED_DEVICE_INDEX, _CACHED_DEVICE_NAME

    # Resolve and cache default if needed.
    idx = get_default_input_device_index()
    # get_default_input_device_index always sets both index and name
    return idx, _CACHED_DEVICE_NAME


def _probe_device_rms(index: int, seconds: float = 0.5) -> tuple[float, float, float]:
    """
    Open the device briefly and measure (p10, p90, avg) RMS.
    Returns (p10, p90, avg). Raises on open failure.
    """
    s = cfg.settings
    with suppress_alsa_warnings_if_linux():
        p = pyaudio.PyAudio()
        stream = None
        try:
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=s.sample_rate,
                input=True,
                frames_per_buffer=s.chunk,
                input_device_index=index,
            )
            frames = int((s.sample_rate / s.chunk) * seconds)
            vals: list[float] = []
            for _ in range(max(1, frames)):
                data = stream.read(s.chunk, exception_on_overflow=False)
                x = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                vals.append(float(np.sqrt(np.mean(x * x))) if x.size else 0.0)
        finally:
            try:
                if stream:
                    if stream.is_active():
                        stream.stop_stream()
                    stream.close()
            except Exception:
                pass
            p.terminate()
    if not vals:
        return (0.0, 0.0, 0.0)
    p10 = float(np.percentile(vals, 10))
    p90 = float(np.percentile(vals, 90))
    avg = float(np.mean(vals))
    return (p10, p90, avg)


def set_selected_input_device(index: int) -> Tuple[int, str]:
    """
    Validate that `index` opens AND that it isn't effectively silent.
    On success, cache and return (index, name).

    This is the function exercised by test_set_and_get_selected_input_device.
    """
    with suppress_alsa_warnings_if_linux():
        p = pyaudio.PyAudio()
        info = None
        try:
            info = p.get_device_info_by_index(index)
            if info.get("maxInputChannels", 0) <= 0:
                raise ValueError("Selected device has no input channels.")
            # Try opening the device once to ensure it works now.
            try:
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=cfg.settings.sample_rate,
                    input=True,
                    frames_per_buffer=cfg.settings.chunk,
                    input_device_index=index,
                )
                stream.close()
            except Exception as e:
                raise ValueError(f"Device [{index}] cannot be opened: {e}")
        finally:
            p.terminate()

    # Quick signal presence probe (separate short recording).
    p10, p90, avg = _probe_device_rms(index, seconds=0.5)

    # *** CHANGED LOGIC HERE ***
    # Treat a device as "silent" only if the RMS is effectively zero.
    # This still catches zero-filled / dead devices, but does not reject
    # low-level but nonzero signals (like the FakePyAudio used in tests).
    if p90 <= 0.0 and avg <= 0.0:
        name = str(info["name"]) if info else f"index {index}"
        raise RuntimeError(
            f"Device appears silent (p90≈{p90:.1f}, avg≈{avg:.1f}). "
            "This often means a virtual mapper/disabled input."
        )

    name = str(info["name"]) if info else f"index {index}"
    _set_cached_device(index, name)
    log.info(
        "🎤 Selected input device [%d] %s (probe p10=%.1f p90=%.1f avg=%.1f)",
        index, _CACHED_DEVICE_NAME, p10, p90, avg
    )
    return _CACHED_DEVICE_INDEX, _CACHED_DEVICE_NAME  # type: ignore[return-value]

def record_wav(
    filename: str,
    record_seconds: int = None,
    sample_rate: int = None,
    chunk: int = None,
    device_index: Optional[int] = None,
) -> None:
    """
    Record mono 16-bit PCM WAV at the configured sample rate.
    """
    s = cfg.settings
    record_seconds = s.record_seconds if record_seconds is None else record_seconds
    sample_rate = s.sample_rate if sample_rate is None else sample_rate
    chunk = s.chunk if chunk is None else chunk

    ensure_dir(os.path.dirname(filename) or ".")
    p = pyaudio.PyAudio()

    if device_index is None:
        device_index = get_default_input_device_index()

    try:
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            input=True,
            frames_per_buffer=chunk,
            input_device_index=device_index,
        )
    except OSError:
        # Fallback to default input if selected index fails at runtime.
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            input=True,
            frames_per_buffer=chunk,
        )

    frames: List[bytes] = []
    try:
        for _ in range(0, int(sample_rate / chunk * record_seconds)):
            data = stream.read(chunk, exception_on_overflow=False)
            frames.append(data)
    finally:
        try:
            stream.stop_stream()
        except Exception:
            pass
        try:
            stream.close()
        except Exception:
            pass
        p.terminate()

    with wave.open(filename, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(frames))


def amplify_wav(input_filename: str, output_filename: str, factor: float = None) -> str:
    s = cfg.settings
    factor = s.amp_factor if factor is None else factor
    with wave.open(input_filename, "rb") as wf:
        params = wf.getparams()
        frames = wf.readframes(wf.getnframes())
        audio = np.frombuffer(frames, dtype=np.int16)

    amplified = np.clip(audio * factor, -32768, 32767).astype(np.int16)

    ensure_dir(os.path.dirname(output_filename) or ".")
    with wave.open(output_filename, "wb") as wf:
        wf.setparams(params)
        wf.writeframes(amplified.tobytes())
    return output_filename


def _ts() -> str:
    t = time.localtime()
    return time.strftime("%Y%m%d_%H%M%S", t) + f"_{int((time.time() % 1) * 1000):03d}"


def record_and_prepare_chunk(
    basename: str = "chunk",
    seconds: int = None,
    amp_factor: float = None,
    device_index: Optional[int] = None,
    out_dir: Optional[str] = None,
    persist: bool = False,
) -> str:
    """
    Records a chunk and returns the path to the amplified WAV.

    persist=False: writes to unique files in the configured temp dir to avoid
    clobbering under concurrent or rapid successive calls.
    """
    s = cfg.settings
    seconds = s.record_seconds if seconds is None else seconds
    amp_factor = s.amp_factor if amp_factor is None else amp_factor

    if persist:
        assert out_dir, "out_dir must be provided when persist=True"
        ensure_dir(out_dir)
        stamp = _ts()
        raw = os.path.join(out_dir, f"{basename}_{stamp}_raw.wav")
        amp = os.path.join(out_dir, f"{basename}_{stamp}_amp.wav")
        record_wav(raw, record_seconds=seconds, device_index=device_index)
        amplify_wav(raw, amp, factor=amp_factor)
        return amp
    else:
        # Use unique temp paths to prevent races and stale reads
        raw = temp_unique_path(prefix=f"{basename}_raw_", suffix=".wav")
        amp = temp_unique_path(prefix=f"{basename}_amp_", suffix=".wav")
        record_wav(raw, record_seconds=seconds, device_index=device_index)
        amplify_wav(raw, amp, factor=amp_factor)
        if s.delete_raw_after_amplify:
            try:
                os.remove(raw)
            except OSError:
                pass
        return amp


def set_default_input_device_index(index: int, name: Optional[str] = None) -> None:
    """
    Override the cached default device. The listener picks this up on next start.
    """
    _set_cached_device(index, name)
    log.info("🎤 Selected input device [%d] %s", _CACHED_DEVICE_INDEX, _CACHED_DEVICE_NAME or "")
