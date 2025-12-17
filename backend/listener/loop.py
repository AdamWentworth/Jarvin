# backend/listener/loop.py

from __future__ import annotations

import logging
from typing import Generator, Optional, Tuple

import numpy as np

import config as cfg
from audio.vad import NoiseGateVAD
from audio.vad.utils import threshold as vad_threshold

log = logging.getLogger("jarvin.audio_loop")


class AudioLoop:
    """
    Thin facade that owns NoiseGateVAD + calibration + utterance iterator.
    No FastAPI/UI dependencies. Blocking API suitable for asyncio.to_thread.
    """

    def __init__(
        self,
        *,
        sample_rate: int,
        chunk: int,
        device_index: Optional[int],
        on_recording=None,
    ) -> None:
        self.sample_rate = sample_rate
        self.chunk = chunk
        self.device_index = device_index
        self._on_recording = on_recording
        self._vad = NoiseGateVAD(
            sample_rate=sample_rate,
            chunk=chunk,
            device_index=device_index,
            on_recording=on_recording,
        )

    def __enter__(self) -> "AudioLoop":
        self._vad.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return self._vad.__exit__(exc_type, exc, tb)

    def request_stop(self) -> None:
        self._vad.request_stop()

    def calibrate(self, seconds: float | None = None) -> None:
        s = cfg.settings
        seconds = s.vad_calibration_sec if seconds is None else seconds
        self._vad.calibrate(seconds)
        log.info("📉 Initial floor RMS=%.1f, threshold≈%.1f", self._vad.floor_rms, vad_threshold(self._vad.floor_rms))

    def utterances(self) -> Generator[Tuple[np.ndarray, int], None, None]:
        """
        Yields (pcm_int16, sample_rate) chunks.
        """
        yield from self._vad.utterances()
