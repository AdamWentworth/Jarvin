# audio/vad/detector.py
from __future__ import annotations

import collections
import logging
import time
from typing import Callable, Deque, Generator, Optional, Tuple

import numpy as np

import config as cfg
from .stream import MicStream
from .utils import TTYStatus, rms_int16, clamp_floor, ema, threshold
from audio.wav_io import write_wav_int16_mono as write_wav

log = logging.getLogger("jarvin.vad")


class NoiseGateVAD:
    """
    Adaptive noise-gate VAD with attack/release/hangover. Emits utterance
    chunks as (pcm_int16, sample_rate).

    Public API:
      - context manager (__enter__/__exit__), open/close/request_stop
      - calibrate(seconds: float | None)
      - utterances() -> Generator[(np.ndarray, int)]
      - write_wav(path, pcm, sample_rate, normalize_dbfs)  # static
    """

    def __init__(
        self,
        sample_rate: int = None,
        chunk: int = None,
        device_index: Optional[int] = None,
        on_recording: Optional[Callable[[bool], None]] = None,
    ) -> None:
        s = cfg.settings
        self.sample_rate = s.sample_rate if sample_rate is None else int(sample_rate)
        self.chunk = s.chunk if chunk is None else int(chunk)
        self.device_index = device_index
        self._mic = MicStream(self.sample_rate, self.chunk, device_index=self.device_index)

        self._stop_requested = False
        self._status = TTYStatus()

        # Frame timing
        self.frame_ms = int((self.chunk / self.sample_rate) * 1000)
        self.alpha_floor = 0.98
        self.alpha_env = 0.85

        # Adaptive state
        self.floor_rms = 50.0
        self.env_rms = 0.0

        # Counters / logs
        self._frame_idx = 0
        self._last_heartbeat_ts = 0.0
        self._last_thr_log_ts = 0.0

        # Callback
        self._on_recording = on_recording

    # ---------- Lifecycle ----------
    def __enter__(self) -> "NoiseGateVAD":
        self.open()
        self._notify_recording(False)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            self.close()
        finally:
            self._notify_recording(False)
        return False

    def open(self) -> None:
        self._mic.open()

    def request_stop(self) -> None:
        self._stop_requested = True
        self._mic.stop()

    def close(self) -> None:
        try:
            self._status.clear()
        except Exception:
            pass
        self._mic.close()

    def _notify_recording(self, flag: bool) -> None:
        try:
            if self._on_recording is not None:
                self._on_recording(flag)
        except Exception:
            pass

    def _read_frame(self) -> np.ndarray:
        if self._stop_requested:
            raise StopIteration
        arr = self._mic.read_frame()
        if self._stop_requested:
            raise StopIteration
        return arr

    # ---------- Calibration ----------
    def calibrate(self, seconds: float = None) -> None:
        s = cfg.settings
        seconds = s.vad_calibration_sec if seconds is None else seconds
        n_frames = max(1, int((seconds * 1000) / self.frame_ms))
        floors = []
        for _ in range(n_frames):
            frame = self._read_frame()
            floors.append(rms_int16(frame))
        base = float(np.percentile(floors, 10))
        self.floor_rms = clamp_floor(base)
        self.env_rms = self.floor_rms
        if cfg.settings.vad_log_transitions:
            p90 = float(np.percentile(floors, 90))
            p10 = float(np.percentile(floors, 10))
            log.info(
                "📉 VAD calibrated | floor=%.1f RMS (p10=%.1f, p90=%.1f) thr≈%.1f",
                self.floor_rms, p10, p90, threshold(self.floor_rms),
            )

    # ---------- Streaming ----------
    def utterances(self) -> Generator[Tuple[np.ndarray, int], None, None]:
        s = cfg.settings
        pre_frames = max(0, int(s.vad_pre_roll_ms / self.frame_ms))
        prebuf: Deque[np.ndarray] = collections.deque(maxlen=pre_frames)

        attack_needed = max(1, int(s.vad_attack_ms / self.frame_ms))
        release_needed = max(1, int(s.vad_release_ms / self.frame_ms))
        hangover_frames = max(0, int(s.vad_hangover_ms / self.frame_ms))
        max_frames = int((s.vad_max_utterance_sec * 1000) / self.frame_ms)

        in_speech = False
        above_cnt = 0
        below_cnt = 0
        hangover = 0
        cur: list[np.ndarray] = []

        while True:
            if self._stop_requested:
                return

            frame = self._read_frame()
            self._frame_idx += 1
            prebuf.append(frame)

            r_inst = rms_int16(frame)
            prev_thr = threshold(self.floor_rms)
            self.env_rms = ema(r_inst, self.env_rms, self.alpha_env)

            thr = threshold(self.floor_rms)
            is_above = (r_inst >= thr) if s.vad_use_instant_rms_for_trigger else (self.env_rms >= thr)

            # idle floor tracking
            if not in_speech and r_inst < (s.vad_floor_adapt_margin * thr):
                new_floor = ema(r_inst, self.floor_rms, self.alpha_floor)
                self.floor_rms = clamp_floor(new_floor)
                now = time.time()
                if s.vad_log_threshold_changes_ms > 0 and (now - self._last_thr_log_ts) * 1000 >= s.vad_log_threshold_changes_ms:
                    if abs(thr - prev_thr) >= 1.0:
                        log.info("↘️  idle | floor=%.1f env=%.1f thr≈%.1f", self.floor_rms, self.env_rms, thr)
                        self._last_thr_log_ts = now

            # optional debug stats
            n = s.vad_log_stats_every_n_frames
            if n and (self._frame_idx % n == 0):
                log.debug(
                    "frame=%d | r=%.1f env=%.1f floor=%.1f thr≈%.1f %s",
                    self._frame_idx, r_inst, self.env_rms, self.floor_rms, thr,
                    "ABOVE" if is_above else "below",
                )

            # heartbeat while waiting
            if not in_speech and s.vad_heartbeat_ms > 0:
                now = time.time()
                if (now - self._last_heartbeat_ts) * 1000 >= s.vad_heartbeat_ms:
                    self._status.update(
                        f"💤 idle | r={r_inst:.1f} env={self.env_rms:.1f} floor={self.floor_rms:.1f} thr≈{thr:.1f} (waiting)"
                    )
                    self._last_heartbeat_ts = now

            # state machine
            if not in_speech:
                above_cnt = above_cnt + 1 if is_above else 0
                if above_cnt >= attack_needed:
                    in_speech = True
                    self._notify_recording(True)
                    hangover = 0
                    cur = list(prebuf)
                    cur.append(frame)
                    below_cnt = 0
                    if s.vad_log_transitions:
                        self._status.clear()
                        log.info(
                            "▶️  START | r=%.1f ≥ thr≈%.1f | attack=%d frames | pre_roll=%d frames",
                            r_inst, thr, attack_needed, len(prebuf),
                        )
                    continue
            else:
                cur.append(frame)
                if is_above:
                    below_cnt = 0
                    hangover = hangover_frames
                else:
                    below_cnt += 1
                    if hangover > 0:
                        hangover -= 1
                        below_cnt = 0

                stop_reason = None
                if below_cnt >= release_needed:
                    stop_reason = f"release {release_needed} frames"
                elif len(cur) >= max_frames:
                    stop_reason = f"max_len {max_frames} frames"

                if stop_reason is not None:
                    pcm = np.concatenate(cur) if cur else np.zeros(0, dtype=np.int16)
                    utt_ms = len(cur) * self.frame_ms

                    if s.vad_log_transitions:
                        try:
                            avg_rms = float(np.mean([rms_int16(f) for f in cur]))
                            peak = int(np.max(np.abs(pcm))) if pcm.size else 0
                        except Exception:
                            avg_rms, peak = 0.0, 0
                        self._status.clear()
                        log.info(
                            "⏹ END  | %s | dur=%.0f ms frames=%d avgRMS=%.1f peak=%d thr≈%.1f",
                            stop_reason, utt_ms, len(cur), avg_rms, peak, thr
                        )

                    self._notify_recording(False)

                    if utt_ms >= s.vad_min_utterance_ms:
                        yield pcm, self.sample_rate
                    else:
                        if s.vad_log_transitions:
                            log.info("🪵 drop | too short (%d ms < %d ms)", int(utt_ms), int(s.vad_min_utterance_ms))

                    in_speech = False
                    above_cnt = 0
                    below_cnt = 0
                    hangover = 0
                    cur = []

    # ----- static passthrough for callers -----
    @staticmethod
    def write_wav(path: str, pcm: np.ndarray, sample_rate: int, normalize_dbfs: Optional[float]) -> None:
        write_wav(path, pcm, sample_rate, normalize_dbfs)
