# backend/util/hw_detect.py
from __future__ import annotations

import platform
import subprocess
from dataclasses import dataclass
from typing import Optional

import psutil

try:
    import torch
except Exception:
    torch = None  # type: ignore[assignment]

@dataclass
class HardwareProfile:
    os: str
    arch: str
    cpu_cores: int
    ram_gb: float
    has_nvidia: bool
    cuda_name: Optional[str]
    vram_gb: Optional[float]
    has_mps: bool


def _torch_cuda_available() -> bool:
    if torch is None:
        return False
    try:
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _nvidia_smi_value(query: str) -> Optional[str]:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=1.0,
        ).strip().splitlines()
        if out:
            return out[0].strip() or None
    except Exception:
        pass
    return None


def _nvidia_vram_gb() -> Optional[float]:
    if _torch_cuda_available():
        try:
            props = torch.cuda.get_device_properties(0)
            return round(props.total_memory / (1024 ** 3), 2)
        except Exception:
            pass
    raw = _nvidia_smi_value("memory.total")
    if raw is not None:
        try:
            return round(float(raw) / 1024.0, 2)
        except Exception:
            pass
    return None


def detect_hardware() -> HardwareProfile:
    os_name = platform.system().lower()
    arch = platform.machine().lower()
    cpu_cores = psutil.cpu_count(logical=True) or 1
    ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 2)

    # --- NVIDIA GPU detection ---
    has_nvidia = _torch_cuda_available()
    cuda_name = None
    vram_gb = None

    if has_nvidia:
        try:
            device = torch.device("cuda:0")
            props = torch.cuda.get_device_properties(device)
            cuda_name = props.name
            vram_gb = round(props.total_memory / (1024 ** 3), 2)
        except Exception:
            cuda_name = None
            vram_gb = None
    else:
        cuda_name = _nvidia_smi_value("name")
        vram_gb = _nvidia_vram_gb()
        has_nvidia = cuda_name is not None or vram_gb is not None

    # --- MPS (macOS Metal) detection ---
    has_mps = False
    if torch is not None:
        try:
            has_mps = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        except Exception:
            has_mps = False

    return HardwareProfile(
        os=os_name,
        arch=arch,
        cpu_cores=cpu_cores,
        ram_gb=ram_gb,
        has_nvidia=has_nvidia,
        cuda_name=cuda_name,
        vram_gb=vram_gb,
        has_mps=has_mps,
    )
