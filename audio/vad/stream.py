# audio/vad/stream.py
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pyaudio

from audio.mic import get_default_input_device_index
from audio.utils import suppress_alsa_warnings_if_linux

log = logging.getLogger("jarvin.vad.stream")


class MicStream:
    """
    Thin wrapper over PyAudio input stream (mono, int16).
    Handles device selection and safe open/close.
    """

    def __init__(self, sample_rate: int, chunk: int, device_index: Optional[int] = None) -> None:
        self.sample_rate = int(sample_rate)
        self.chunk = int(chunk)
        self.device_index = device_index
        self._pa: Optional[pyaudio.PyAudio] = None
        self._stream: Optional[pyaudio.Stream] = None

    def open(self) -> None:
        if self._pa:
            return
        self._pa = pyaudio.PyAudio()
        if self.device_index is None:
            self.device_index = get_default_input_device_index()
        with suppress_alsa_warnings_if_linux():
            try:
                self._stream = self._pa.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self.sample_rate,
                    input=True,
                    frames_per_buffer=self.chunk,
                    input_device_index=self.device_index,
                )
            except OSError:
                # Fallback: default input device
                self._stream = self._pa.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self.sample_rate,
                    input=True,
                    frames_per_buffer=self.chunk,
                )
                log.warning("MicStream: requested index=%s failed; fell back to system default.", self.device_index)

    def read_frame(self) -> np.ndarray:
        assert self._stream is not None, "MicStream not open"
        data = self._stream.read(self.chunk, exception_on_overflow=False)
        return np.frombuffer(data, dtype=np.int16)

    def stop(self) -> None:
        try:
            if self._stream and self._stream.is_active():
                self._stream.stop_stream()
        except Exception:
            pass

    def close(self) -> None:
        try:
            if self._stream:
                try:
                    if self._stream.is_active():
                        self._stream.stop_stream()
                except Exception:
                    pass
                self._stream.close()
        finally:
            self._stream = None
            if self._pa:
                self._pa.terminate()
                self._pa = None
