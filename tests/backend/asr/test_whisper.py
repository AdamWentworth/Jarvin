from __future__ import annotations

import wave

import numpy as np

import backend.asr.whisper as whisper_mod


def test_load_audio_waveform_uses_wav_fast_path(monkeypatch):
    expected = np.array([0.1, -0.2], dtype=np.float32)

    monkeypatch.setattr(whisper_mod, "wav_to_float32_mono_16k", lambda _: expected)

    def _unexpected_load_audio(_: str):
        raise AssertionError("whisper.load_audio should not be used for valid wav input")

    monkeypatch.setattr(whisper_mod.whisper, "load_audio", _unexpected_load_audio)

    actual = whisper_mod._load_audio_waveform("clip.wav")

    assert np.array_equal(actual, expected)


def test_load_audio_waveform_falls_back_to_whisper_decoder(monkeypatch):
    expected = np.array([0.25, -0.25], dtype=np.float32)

    def _bad_wav(_: str):
        raise wave.Error("file does not start with RIFF id")

    monkeypatch.setattr(whisper_mod, "wav_to_float32_mono_16k", _bad_wav)
    monkeypatch.setattr(whisper_mod.whisper, "load_audio", lambda _: expected)

    actual = whisper_mod._load_audio_waveform("clip.webm")

    assert np.array_equal(actual, expected)
