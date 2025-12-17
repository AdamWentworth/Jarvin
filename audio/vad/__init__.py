# audio/vad/__init__.py
from __future__ import annotations

from .detector import NoiseGateVAD  # public façade

__all__ = ["NoiseGateVAD"]
