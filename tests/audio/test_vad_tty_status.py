from __future__ import annotations

import config as cfg
from audio.vad.utils import TTYStatus


class Cp1252TTY:
    encoding = "cp1252"

    def __init__(self) -> None:
        self.output = ""

    def isatty(self) -> bool:
        return True

    def write(self, text: str) -> int:
        text.encode(self.encoding)
        self.output += text
        return len(text)

    def flush(self) -> None:
        return None


def test_tty_status_replaces_unencodable_unicode(monkeypatch):
    stream = Cp1252TTY()
    monkeypatch.setattr(cfg.settings, "vad_tty_status", True, raising=True)
    monkeypatch.setattr("audio.vad.utils.sys.stderr", stream)

    status = TTYStatus()
    status.update("💤 idle | threshold≈200")

    assert status.enabled is True
    assert "idle" in stream.output
    assert "?" in stream.output


def test_tty_status_disables_itself_when_stream_write_fails(monkeypatch):
    class BrokenTTY(Cp1252TTY):
        def write(self, text: str) -> int:
            raise OSError("stream closed")

    monkeypatch.setattr(cfg.settings, "vad_tty_status", True, raising=True)
    monkeypatch.setattr("audio.vad.utils.sys.stderr", BrokenTTY())

    status = TTYStatus()
    status.update("idle")

    assert status.enabled is False
