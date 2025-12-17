# scripts/list_mics_safe.py
from __future__ import annotations

import pyaudio
from audio.utils import suppress_alsa_warnings_if_linux


def main():
    with suppress_alsa_warnings_if_linux():
        p = pyaudio.PyAudio()
        try:
            print("Available input devices:")
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if info.get("maxInputChannels", 0) > 0:
                    name = info["name"]
                    rate = int(info.get("defaultSampleRate", 0))
                    print(f"[{i}] {name} | Default rate: {rate} Hz")
        finally:
            p.terminate()


if __name__ == "__main__":
    main()
