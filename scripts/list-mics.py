# scripts/list-mics.py
from __future__ import annotations

import sys
import pyaudio
from audio.utils import suppress_alsa_warnings_if_linux


def _list_input_devices() -> list[tuple[int, str]]:
    """All input-capable devices: [(index, name)]."""
    devices: list[tuple[int, str]] = []
    p = pyaudio.PyAudio()
    try:
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                devices.append((i, info["name"]))
    finally:
        p.terminate()
    return devices


def list_working_input_devices(rate: int = 16_000, chunk: int = 1024) -> list[tuple[int, str]]:
    """
    Return devices that can actually open a mono stream at `rate` Hz.
    """
    working: list[tuple[int, str]] = []
    p = pyaudio.PyAudio()
    try:
        for idx, name in _list_input_devices():
            try:
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=rate,
                    input=True,
                    input_device_index=idx,
                    frames_per_buffer=chunk,
                )
                stream.close()
                working.append((idx, name))
            except Exception:
                continue
    finally:
        p.terminate()
    return working


if __name__ == "__main__":
    with suppress_alsa_warnings_if_linux():
        devices = list_working_input_devices()

    if not devices:
        print("No working input devices at 16 kHz mono.")
        sys.exit(1)

    print("Working input devices (16 kHz mono):")
    for idx, name in devices:
        print(f"[{idx}] {name}")
