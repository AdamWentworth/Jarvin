from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import platform
import subprocess
import sys
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.util.windows_dll import prime_windows_gpu_dll_search_path  # noqa: E402


def _print_section(title: str) -> None:
    print()
    print(f"[{title}]")


def _run_nvidia_smi() -> None:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5.0,
        ).strip()
        print(out or "nvidia-smi returned no rows")
    except Exception as exc:
        print(f"nvidia-smi unavailable: {exc}")


def _print_env() -> None:
    for name in (
        "JARVIN_WHISPER_MODEL_SIZE",
        "JARVIN_LLM_N_GPU_LAYERS",
        "JARVIN_LLM_VERBOSE",
        "JARVIN_LLM_LOG_SYSTEM_INFO",
        "JARVIN_LLM_REQUIRE_GPU",
        "CUDA_PATH",
    ):
        print(f"{name}={os.getenv(name)}")


def _print_torch() -> None:
    try:
        import torch

        print(f"version={torch.__version__}")
        print(f"cuda_available={torch.cuda.is_available()}")
        print(f"cuda_version={torch.version.cuda}")
        print(f"device_count={torch.cuda.device_count()}")
        if torch.cuda.is_available():
            print(f"device_name={torch.cuda.get_device_name(0)}")

        spec = importlib.util.find_spec("torch")
        if spec and spec.origin:
            torch_lib = Path(spec.origin).resolve().parent / "lib"
            print(f"torch_lib={torch_lib}")
            print(f"torch_has_cudart64_12={str((torch_lib / 'cudart64_12.dll').exists()).lower()}")
            print(f"torch_has_cublas64_12={str((torch_lib / 'cublas64_12.dll').exists()).lower()}")
    except Exception:
        traceback.print_exc()


def _print_whisper() -> None:
    try:
        import whisper

        print(f"version={getattr(whisper, '__version__', 'unknown')}")
    except Exception:
        traceback.print_exc()


def _print_llama_cpp() -> None:
    dll_dirs = prime_windows_gpu_dll_search_path()
    if dll_dirs:
        print("primed_dll_dirs=")
        for path in dll_dirs:
            print(f"  {path}")

    try:
        import llama_cpp

        print(f"version={getattr(llama_cpp, '__version__', None)}")

        info = None
        if hasattr(llama_cpp, "llama_get_system_info"):
            raw = llama_cpp.llama_get_system_info()  # type: ignore[attr-defined]
            info = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
        elif hasattr(llama_cpp, "llama_print_system_info"):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                llama_cpp.llama_print_system_info()  # type: ignore[attr-defined]
            info = buf.getvalue()

        print((info or "NO_SYSTEM_INFO").strip())
    except Exception:
        traceback.print_exc()


def main() -> int:
    print(f"python={sys.version.split()[0]}")
    print(f"platform={platform.platform()}")
    print(f"executable={sys.executable}")
    print(f"repo_root={ROOT}")

    _print_section("env")
    _print_env()

    _print_section("nvidia-smi")
    _run_nvidia_smi()

    _print_section("torch")
    _print_torch()

    _print_section("whisper")
    _print_whisper()

    _print_section("llama-cpp-python")
    _print_llama_cpp()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
