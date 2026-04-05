# backend/core/pipeline.py
from __future__ import annotations

import time
from typing import Optional, Tuple, Dict
import numpy as np

import config as cfg
from backend.core.ports import ASRTranscriber, LLMChatEngine, AudioSink
from audio.wav_io import write_wav_int16_mono as _write_wav_int16_mono
from backend.util.paths import temp_unique_path
from backend.ai_engine import JarvinConfig, build_context, build_jarvin_config
from backend.agent.voice.voice_listener_clarification_state import resolve_listener_voice_review
from backend.asr.whisper import WhisperASR
from backend.llm.runtime_local import LocalChat
from backend.tts.engine import synth_to_wav
from memory.conversation import (
    get_conversation_history,
    get_user_profile,
    append_turn,
)

class _FnSink:
    @staticmethod
    def write_wav(path: str, pcm: np.ndarray, sample_rate: int, normalize_dbfs: float | None) -> None:
        _write_wav_int16_mono(path, pcm, sample_rate, normalize_dbfs)


def _transcribe_with_best_path(
    asr: ASRTranscriber,
    *,
    pcm: np.ndarray,
    sample_rate: int,
    wav_path: str,
    sink: AudioSink,
    normalize_dbfs: float | None,
) -> str:
    transcribe_pcm = getattr(asr, "transcribe_pcm", None)
    if callable(transcribe_pcm):
        text = transcribe_pcm(pcm, sample_rate, normalize_dbfs=normalize_dbfs)
        sink.write_wav(wav_path, pcm, sample_rate, normalize_dbfs)
        return text

    sink.write_wav(wav_path, pcm, sample_rate, normalize_dbfs)
    return asr.transcribe(wav_path)


def process_utterance(
    pcm: np.ndarray,
    sr: int,
    *,
    model=None,
    device: str = "cpu",
    cfg_ai: Optional[JarvinConfig] = None,
    asr: Optional[ASRTranscriber] = None,
    llm: Optional[LLMChatEngine] = None,
    audio_sink: Optional[AudioSink] = None,
) -> Tuple[str, str, Dict[str, int], str, Optional[str]]:
    s = cfg.settings
    cfg_ai = cfg_ai or build_jarvin_config()

    # Unique path per utterance to avoid overwriting when multiple cycles run quickly
    wav_path = temp_unique_path(prefix="live_utt_", suffix=".wav")
    sink = audio_sink or _FnSink()

    utt_ms = int((len(pcm) / max(1, sr)) * 1000)

    if asr is None:
        if model is not None:
            class _LegacyASR:
                def transcribe(self, path: str) -> str:
                    from audio.speech_recognition import transcribe_audio as _t
                    return _t(path, model=model, device=device)
            asr = _LegacyASR()
        else:
            asr = WhisperASR(s.whisper_model_size)

    if llm is None:
        class _LLMWithCfg:
            def __init__(self, base: LocalChat, cfg_ai: JarvinConfig) -> None:
                self._base = base
                self._cfg = cfg_ai
            def reply(self, user_text: str, *, context: Optional[str] = None) -> str:
                from backend.ai_engine import generate_reply as _gen
                return _gen(user_text, cfg=self._cfg, context=context)
        llm = _LLMWithCfg(LocalChat(), cfg_ai)

    t0 = time.perf_counter()
    raw_text = _transcribe_with_best_path(
        asr,
        pcm=pcm,
        sample_rate=sr,
        wav_path=wav_path,
        sink=sink,
        normalize_dbfs=s.normalize_to_dbfs,
    ).strip()
    t_trans_ms = int((time.perf_counter() - t0) * 1000)

    review_decision = resolve_listener_voice_review(raw_text)
    text = review_decision.transcript_for_display or raw_text
    acted_text = (review_decision.acted_text or "").strip()
    reply = ""
    t_reply_ms = 0
    tts_path: Optional[str] = None
    if review_decision.spoken_reply:
        reply = review_decision.spoken_reply
    elif acted_text:
        # Build compact context for the LLM from in-process memory
        profile = get_user_profile()
        history = get_conversation_history()
        ctx = build_context(profile=profile, history=history, max_turns=cfg_ai.history_window)

        t1 = time.perf_counter()
        reply = llm.reply(acted_text, context=ctx) or ""
        t_reply_ms = int((time.perf_counter() - t1) * 1000)

        # Persist this turn for future context
        if review_decision.should_persist_turn:
            append_turn("user", acted_text)
        if reply:
            append_turn("assistant", reply)

    # Synthesize reply if available (non-fatal if it fails)
    if reply:
        try:
            tts_path = synth_to_wav(reply)
        except Exception:
            tts_path = None

    timings = {
        "utter_ms": utt_ms,
        "transcribe_ms": t_trans_ms,
        "reply_ms": t_reply_ms,
    }
    return text, reply, timings, wav_path, tts_path
