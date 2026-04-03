from __future__ import annotations

from pathlib import Path

import numpy as np

from backend.core import pipeline


class _FakeSink:
    def __init__(self) -> None:
        self.calls: list[tuple[str, np.ndarray, int, float | None]] = []

    def write_wav(self, path: str, pcm: np.ndarray, sample_rate: int, normalize_dbfs: float | None) -> None:
        self.calls.append((path, pcm.copy(), sample_rate, normalize_dbfs))


class _PCMFirstASR:
    def __init__(self) -> None:
        self.pcm_calls: list[tuple[np.ndarray, int, float | None]] = []

    def transcribe_pcm(self, pcm: np.ndarray, sample_rate: int, normalize_dbfs: float | None = None) -> str:
        self.pcm_calls.append((pcm.copy(), sample_rate, normalize_dbfs))
        return "hello there"

    def transcribe(self, wav_path: str) -> str:
        raise AssertionError("file-path transcription should not be used when transcribe_pcm exists")


class _PathOnlyASR:
    def __init__(self) -> None:
        self.paths: list[str] = []

    def transcribe(self, wav_path: str) -> str:
        self.paths.append(wav_path)
        return "fallback path"


class _FakeLLM:
    def reply(self, user_text: str, *, context: str | None = None) -> str:
        return "general kenobi"


def _patch_pipeline_side_effects(monkeypatch) -> None:
    monkeypatch.setattr(pipeline, "temp_unique_path", lambda prefix, suffix: str(Path("temp") / "live_utt_test.wav"))
    monkeypatch.setattr(pipeline, "get_user_profile", lambda: {})
    monkeypatch.setattr(pipeline, "get_conversation_history", lambda: [])
    monkeypatch.setattr(pipeline, "append_turn", lambda role, text: None)
    monkeypatch.setattr(pipeline, "synth_to_wav", lambda text: None)


def test_process_utterance_prefers_in_memory_asr(monkeypatch):
    _patch_pipeline_side_effects(monkeypatch)
    sink = _FakeSink()
    asr = _PCMFirstASR()
    pcm = np.array([0, 1000, -1000, 2000], dtype=np.int16)

    text, reply, timings, wav_path, tts_path = pipeline.process_utterance(
        pcm,
        16000,
        asr=asr,
        llm=_FakeLLM(),
        audio_sink=sink,
    )

    assert text == "hello there"
    assert reply == "general kenobi"
    assert timings["utter_ms"] == 0
    assert wav_path.endswith("live_utt_test.wav")
    assert tts_path is None
    assert len(asr.pcm_calls) == 1
    _, sample_rate, normalize_dbfs = asr.pcm_calls[0]
    assert sample_rate == 16000
    assert normalize_dbfs == pipeline.cfg.settings.normalize_to_dbfs
    assert len(sink.calls) == 1
    assert sink.calls[0][0] == wav_path


def test_process_utterance_falls_back_to_wav_path_asr(monkeypatch):
    _patch_pipeline_side_effects(monkeypatch)
    sink = _FakeSink()
    asr = _PathOnlyASR()
    pcm = np.array([0, 1000, -1000, 2000], dtype=np.int16)

    text, reply, timings, wav_path, tts_path = pipeline.process_utterance(
        pcm,
        16000,
        asr=asr,
        llm=_FakeLLM(),
        audio_sink=sink,
    )

    assert text == "fallback path"
    assert reply == "general kenobi"
    assert timings["utter_ms"] == 0
    assert wav_path.endswith("live_utt_test.wav")
    assert tts_path is None
    assert asr.paths == [wav_path]
    assert len(sink.calls) == 1
    assert sink.calls[0][0] == wav_path
