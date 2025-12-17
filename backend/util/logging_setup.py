# backend/util/logging_setup.py
from __future__ import annotations

import logging
import sys
from typing import Optional

_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

def init_logging(level: Optional[str] = None) -> None:
    lvl_name = (level or "info").lower()
    lvl = _LEVELS.get(lvl_name, logging.INFO)

    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    root.addHandler(handler)
    root.setLevel(lvl)
