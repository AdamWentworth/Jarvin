# backend/util/paths.py
from __future__ import annotations

import os
import uuid

import config as cfg

def ensure_temp_dir() -> str:
    path = os.path.abspath(cfg.settings.temp_dir)
    os.makedirs(path, exist_ok=True)
    return path

def temp_path(name: str) -> str:
    root = ensure_temp_dir()
    return os.path.join(root, name)

def temp_unique_path(prefix: str = "up_", suffix: str = ".tmp") -> str:
    root = ensure_temp_dir()
    return os.path.join(root, f"{prefix}{uuid.uuid4().hex}{suffix}")
