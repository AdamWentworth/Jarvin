# record_and_transcribe.py
from __future__ import annotations

import time

import config as cfg
from audio.mic import record_and_prepare_chunk
from backend.asr.whisper import transcribe_audio, _get_model_and_device as get_cached_model_and_device


def main():
    s = cfg.settings
    model, device = get_cached_model_and_device(None)
    print(f"🧠 Model ready on {device}")

    try:
        while True:
            amp_wav = record_and_prepare_chunk(
                basename="cli",
                seconds=s.record_seconds,
                amp_factor=s.amp_factor,
            )
            text = transcribe_audio(amp_wav, model=model, device=device)
            print("🗣️ You said:", text)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Exiting...")


if __name__ == "__main__":
    main()
