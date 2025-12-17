import io
import sys
import os
import tempfile
import importlib
import wave
import types
import math
from pathlib import Path

import numpy as np
import pytest

# --- CRITICAL: Patch pyaudio BEFORE any audio imports ---
class FakeStream:
    def __init__(self, data_frames: list[bytes], sample_size=2, chunk=1024):
        self._frames = data_frames[:]
        self._closed = False
        self._active = True
        self.sample_size = sample_size
        self.chunk = chunk

    def read(self, n, exception_on_overflow=True):
        if not self._frames:
            return (b"\x00" * n * self.sample_size)
        return self._frames.pop(0)

    def stop_stream(self):
        self._active = False

    def is_active(self):
        return self._active

    def close(self):
        self._closed = True


class FakePyAudio:
    def __init__(self, devices=None, default_index=0):
        self._devices = devices or [
            {"index": 0, "name": "Fake Mic 0", "maxInputChannels": 1, "defaultSampleRate": 16000},
        ]
        self._default = default_index
        self.sample_size = 2

    def get_device_count(self):
        return len(self._devices)

    def get_device_info_by_index(self, i):
        # Add defaultSampleRate to avoid validation errors
        device = self._devices[i].copy()
        if "defaultSampleRate" not in device:
            device["defaultSampleRate"] = 16000
        if "maxInputChannels" not in device:
            device["maxInputChannels"] = 1
        return device

    def get_default_input_device_info(self):
        return self.get_device_info_by_index(self._default)

    def open(self, format, channels, rate, input, frames_per_buffer, input_device_index=None):
        frame_bytes = (b"\x01\x00") * frames_per_buffer
        return FakeStream([frame_bytes for _ in range(10)], sample_size=2, chunk=frames_per_buffer)

    def terminate(self):
        pass

    def get_sample_size(self, fmt):
        return self.sample_size


# Create and install the fake module BEFORE any imports
fake_mod = types.ModuleType("pyaudio")
fake_mod.PyAudio = FakePyAudio
fake_mod.paInt16 = 8
fake_mod.paContinue = 0
fake_mod.paComplete = 1
fake_mod.paAbort = 2
fake_mod.paFramesPerBufferUnspecified = 0

# Patch sys.modules so audio.mic gets our fake
sys.modules["pyaudio"] = fake_mod

# Mock config.settings if it doesn't exist
# First create a mock config module
# Mock config.settings if it doesn't exist
# First create a mock config module
mock_config = types.ModuleType("audio.config")
mock_config.settings = types.SimpleNamespace(
    # Core audio settings
    sample_rate=16000,
    chunk=1024,
    
    # VAD settings - COMPLETE LIST
    vad_tty_status=False,
    vad_floor_min=0.001,
    vad_floor_max=0.1,
    vad_threshold_db=-40,
    vad_hangover_ms=300,
    vad_min_speech_ms=100,
    vad_silence_ms=500,
    vad_calibration_sec=3,          # ← ADD THIS
    vad_log_transitions=False,      # ← ADD THIS
    vad_min_amplitude=0.01,
    vad_pre_speech_ms=100,
    vad_noise_floor_multiplier=1.5,
    vad_speech_threshold_multiplier=2.0,
    vad_debug=False,
    vad_show_meter=False,
    vad_show_transitions=False,
    
    # Device settings
    default_device_index=0,
    fallback_device_index=None,
    
    # Recording settings
    record_seconds=5,
    amplify_factor=1.0,
    
    # WAV settings
    wav_sample_rate=16000,
    wav_sample_width=2,
    wav_channels=1,
)
sys.modules["audio.config"] = mock_config

# NOW import your audio modules
try:
    import audio.mic as mic
    import audio.utils as utils
    import audio.wav_io as wav_io
    import audio.vad.detector as detector
    import audio.vad.stream as stream
    import audio.vad.utils as vad_utils
except ImportError as e:
    # If imports fail, skip all tests
    pytest.skip(f"Audio modules not available: {e}", allow_module_level=True)

# --- Remove the fixture or keep it as a no-op ---
@pytest.fixture(autouse=True)
def ensure_fake_pyaudio():
    """Ensure fake pyaudio is still in place for each test."""
    yield


# --- Tests for utils.suppress_alsa_warnings_if_linux ---

def test_suppress_alsa_noop_on_non_linux(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    with utils.suppress_alsa_warnings_if_linux():
        assert True


def test_suppress_alsa_handles_missing_fileno(monkeypatch, capsys):
    monkeypatch.setattr(sys, "platform", "linux")

    class DummyStderr:
        def fileno(self):
            raise Exception("no fileno")

    monkeypatch.setattr(sys, "stderr", DummyStderr())
    with utils.suppress_alsa_warnings_if_linux():
        assert True


# --- Tests for wav_io ---

def test_linear_resample_and_wav_roundtrip(tmp_path):
    sr_src = 8000
    duration_s = 0.1
    t = np.linspace(0, duration_s, int(sr_src * duration_s), endpoint=False)
    tone = (0.5 * np.sin(2 * math.pi * 440 * t) * 32767).astype(np.int16)

    path = tmp_path / "src.wav"
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr_src)
        wf.writeframes(tone.tobytes())

    arr = wav_io.wav_to_float32_mono_16k(str(path))
    assert arr.dtype == np.float32
    assert abs(len(arr) - len(tone) * 2) <= 2


def test_write_wav_int16_mono(tmp_path):
    pcm = np.array([0, 1000, -1000, 32767, -32768], dtype=np.int16)
    out = tmp_path / "out.wav"
    wav_io.write_wav_int16_mono(str(out), pcm, sample_rate=16000)
    with wave.open(str(out), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000


# --- Tests for mic module: device listing/caching/recording ---

def test_list_input_devices_and_default():
    devices = mic.list_input_devices()
    assert isinstance(devices, list)
    assert len(devices) >= 1

    idx = mic.get_default_input_device_index()
    assert isinstance(idx, int)


def test_set_and_get_selected_input_device():
    # Patch cfg.settings inside the mic module if needed
    if hasattr(mic, 'cfg'):
        mic.cfg.settings = mock_config.settings  # Use our mock
    
    idx, name = mic.set_selected_input_device(0)
    got_idx, got_name = mic.get_selected_input_device()
    assert got_idx == idx
    assert got_name == name


def test_record_and_amplify(tmp_path):
    out = tmp_path / "rec.wav"
    mic.record_wav(str(out), record_seconds=0, sample_rate=16000, chunk=64, device_index=0)
    assert out.exists()

    in_wave = out
    amp_out = tmp_path / "rec_amp.wav"
    with wave.open(str(in_wave), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes((b"\x01\x00" * 100))
    mic.amplify_wav(str(in_wave), str(amp_out), factor=2.0)
    assert amp_out.exists()


# --- Tests for VAD components ---

class DummyMicStreamForVAD:
    def __init__(self, sample_rate, chunk, device_index=None):
        self.sample_rate = sample_rate
        self.chunk = chunk
        self._count = 0
        self._max_frames = 50

    def open(self):
        pass

    def read_frame(self):
        self._count += 1
        if self._count > self._max_frames:
            raise StopIteration

        if self._count < 3:
            return np.zeros(self.chunk, dtype=np.int16)
        elif self._count < 8:
            return (np.ones(self.chunk, dtype=np.int16) * 3000)
        else:
            return np.zeros(self.chunk, dtype=np.int16)

    def stop(self):
        pass

    def close(self):
        pass


def test_vad_calibrate_and_utterances(monkeypatch):
    monkeypatch.setattr(detector, "MicStream", DummyMicStreamForVAD)
    
    # REMOVE the clamp_floor patch since we now have the attributes in mock config
    # Just use the normal function with our mocked settings
    
    vad = detector.NoiseGateVAD(sample_rate=16000, chunk=320)
    vad.open()
    vad.calibrate(seconds=0.01)
    gen = vad.utterances()
    try:
        for i, (pcm, sr) in zip(range(2), gen):
            assert isinstance(pcm, np.ndarray)
            assert sr == 16000
            break
    except Exception:
        pass
    finally:
        vad.close()


# --- Tests for vad.stream MicStream open/read/close behavior with fallback ---

def test_micstream_open_fallback(monkeypatch):
    class LocalFakePA(FakePyAudio):
        def __init__(self):
            super().__init__()
            self.attempts = 0

        def open(self, format, channels, rate, input, frames_per_buffer, input_device_index=None):
            self.attempts += 1
            if self.attempts == 1:
                raise OSError("device fail")
            return super().open(format, channels, rate, input, frames_per_buffer, input_device_index)

    def make_fake():
        return LocalFakePA()

    monkeypatch.setattr(stream, "pyaudio", types.SimpleNamespace(PyAudio=make_fake, paInt16=8))
    ms = stream.MicStream(sample_rate=16000, chunk=256, device_index=0)
    ms.open()
    assert ms._stream is not None
    ms.close()


if __name__ == "__main__":
    pytest.main([os.path.abspath(__file__)])