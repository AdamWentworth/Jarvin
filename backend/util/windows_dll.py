from __future__ import annotations

import importlib.util
import os
import site
from pathlib import Path
from typing import Iterable


def _unique_existing_dirs(paths: Iterable[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []

    for path in paths:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path

        if not resolved.is_dir():
            continue

        key = os.path.normcase(str(resolved))
        if key in seen:
            continue

        seen.add(key)
        out.append(resolved)

    return out


def _torch_lib_dir() -> list[Path]:
    spec = importlib.util.find_spec("torch")
    if spec is None or spec.origin is None:
        return []
    return [Path(spec.origin).resolve().parent / "lib"]


def _nvidia_python_runtime_dirs() -> list[Path]:
    roots: list[Path] = []

    try:
        roots.extend(Path(p) for p in site.getsitepackages())
    except Exception:
        pass

    try:
        user_site = site.getusersitepackages()
    except Exception:
        user_site = None

    if user_site:
        roots.append(Path(user_site))

    out: list[Path] = []
    for root in roots:
        nvidia_root = root / "nvidia"
        if not nvidia_root.is_dir():
            continue

        for package_dir in nvidia_root.iterdir():
            if not package_dir.is_dir():
                continue
            out.append(package_dir / "bin")
            out.append(package_dir / "lib")

    return out


def windows_gpu_runtime_dirs() -> list[Path]:
    candidates: list[Path] = []

    cuda_path = os.getenv("CUDA_PATH")
    if cuda_path:
        cuda_root = Path(cuda_path)
        candidates.extend(
            [
                cuda_root / "bin",
                cuda_root / "lib",
                cuda_root / "lib" / "x64",
            ]
        )

    candidates.extend(_torch_lib_dir())
    candidates.extend(_nvidia_python_runtime_dirs())

    return _unique_existing_dirs(candidates)


def prime_windows_gpu_dll_search_path() -> list[str]:
    """
    Add common CUDA runtime directories to the Windows DLL search path.

    This is mainly needed for llama-cpp-python GPU wheels, which can depend on
    CUDA DLLs shipped by either a local CUDA Toolkit install or Python wheels
    such as torch / nvidia-*-cu12.
    """
    if os.name != "nt":
        return []

    added: list[str] = []
    current_path = os.environ.get("PATH", "")
    current_entries = current_path.split(os.pathsep) if current_path else []

    for directory in windows_gpu_runtime_dirs():
        path_str = str(directory)

        try:
            os.add_dll_directory(path_str)
        except (AttributeError, FileNotFoundError, OSError):
            pass

        if not any(os.path.normcase(entry) == os.path.normcase(path_str) for entry in current_entries):
            current_entries.insert(0, path_str)
            added.append(path_str)

    if current_entries:
        os.environ["PATH"] = os.pathsep.join(current_entries)

    return added
