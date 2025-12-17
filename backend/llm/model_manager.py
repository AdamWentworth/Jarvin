# backend/llm/model_manager.py
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Optional, List

try:
    from huggingface_hub import snapshot_download
except Exception:
    snapshot_download = None  # type: ignore

import config as cfg
from backend.util.hw_detect import HardwareProfile, detect_hardware

@dataclass
class GGUFModelSpec:
    logical_name: str
    repo_id: str
    filename: str
    params_b: int
    quant: str
    mem_req_gb: float

def _registry(profile: HardwareProfile) -> List[GGUFModelSpec]:
    ram = profile.ram_gb
    candidates: List[GGUFModelSpec] = []

    if ram >= 8.0:
        candidates.append(GGUFModelSpec(
            logical_name="mistral-7b-instruct",
            repo_id="TheBloke/Mistral-7B-Instruct-v0.2-GGUF",
            filename="mistral-7b-instruct-v0.2.Q4_K_M.gguf",
            params_b=7,
            quant="Q4_K_M",
            mem_req_gb=6.0,
        ))

    candidates.append(GGUFModelSpec(
        logical_name="phi-3-mini-4k-instruct",
        repo_id="microsoft/Phi-3-mini-4k-instruct-gguf",
        filename="Phi-3-mini-4k-instruct-q4.gguf",
        params_b=3,
        quant="Q4",
        mem_req_gb=4.0,
    ))

    if ram >= 8.0:
        candidates.append(GGUFModelSpec(
            logical_name="neural-chat-7b",
            repo_id="TheBloke/Neural-Chat-7B-v3-1-GGUF",
            filename="neural-chat-7b-v3-1.Q4_K_M.gguf",
            params_b=7,
            quant="Q4_K_M",
            mem_req_gb=6.0,
        ))

    pref_index = {name: i for i, name in enumerate(cfg.settings.llm_model_preference)}
    candidates.sort(key=lambda m: (pref_index.get(m.logical_name, 1_000), m.mem_req_gb))
    return candidates

def get_spec_by_logical_name(name: str, profile: Optional[HardwareProfile] = None) -> GGUFModelSpec:
    profile = profile or detect_hardware()
    for spec in _registry(profile):
        if spec.logical_name == name:
            return spec
    raise ValueError(f"Unknown logical model name: {name}")

def pick_model(profile: Optional[HardwareProfile] = None) -> GGUFModelSpec:
    s = cfg.settings
    profile = profile or detect_hardware()
    if s.llm_force_logical_name:
        return get_spec_by_logical_name(s.llm_force_logical_name, profile)
    candidates = _registry(profile)
    if not candidates:
        raise RuntimeError("No GGUF candidates available for this hardware.")
    return candidates[0]

def _validate_gguf(path: str) -> bool:
    try:
        if not os.path.exists(path):
            return False
        if os.path.getsize(path) < 10 * 1024 * 1024:
            return False
        with open(path, "rb") as f:
            mag = f.read(4)
        return mag in (b"GGUF", b"gguf")
    except Exception:
        return False

def _find_file(root: str, filename: str) -> Optional[str]:
    for dirpath, _dirnames, filenames in os.walk(root):
        if filename in filenames:
            return os.path.join(dirpath, filename)
    return None

def ensure_download(spec: GGUFModelSpec, models_dir: Optional[str] = None) -> str:
    if snapshot_download is None:
        raise RuntimeError("huggingface-hub is not installed; cannot download models.")

    s = cfg.settings
    models_dir = models_dir or s.models_dir
    os.makedirs(models_dir, exist_ok=True)

    flat_path = os.path.abspath(os.path.join(models_dir, spec.filename)) if s.llm_flat_layout else None

    if flat_path and _validate_gguf(flat_path):
        return flat_path

    snapshot_root = snapshot_download(
        repo_id=spec.repo_id,
        local_dir=models_dir,
        allow_patterns=[spec.filename],
    )

    sr_abs = os.path.abspath(snapshot_root)
    md_abs = os.path.abspath(models_dir)

    src = _find_file(snapshot_root, spec.filename)
    if not src and sr_abs == md_abs:
        candidate = os.path.join(md_abs, spec.filename)
        if os.path.exists(candidate):
            src = candidate

    if not src:
        raise RuntimeError(f"Downloaded snapshot did not contain {spec.filename}: {snapshot_root}")

    if s.llm_flat_layout and flat_path:
        if os.path.abspath(src) != flat_path:
            shutil.copy2(src, flat_path)

        if not _validate_gguf(flat_path):
            try:
                os.remove(flat_path)
            except Exception:
                pass
            raise RuntimeError(f"Downloaded model appears invalid/corrupt: {flat_path}")

        if s.llm_clean_vendor_dirs:
            try:
                if os.path.isdir(sr_abs) and os.path.commonpath([sr_abs, md_abs]) == md_abs and sr_abs != md_abs:
                    flat_dir = os.path.dirname(flat_path)
                    if os.path.normcase(sr_abs) != os.path.normcase(flat_dir):
                        shutil.rmtree(sr_abs, ignore_errors=True)
            except Exception:
                pass
            try:
                dot_cache = os.path.join(md_abs, ".cache")
                if os.path.isdir(dot_cache) and os.path.commonpath([dot_cache, md_abs]) == md_abs:
                    shutil.rmtree(dot_cache, ignore_errors=True)
            except Exception:
                pass

        return flat_path

    if not _validate_gguf(src):
        raise RuntimeError(f"Downloaded model appears invalid/corrupt: {src}")
    return os.path.abspath(src)
