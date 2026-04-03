# backend/llm/runtime_llama_cpp.py
from __future__ import annotations

import contextlib
import io
import logging
import os
from functools import lru_cache
from typing import List, Dict, Optional, TYPE_CHECKING, Tuple

import config as cfg
from backend.llm.model_manager import pick_model, ensure_download, GGUFModelSpec
from backend.util.windows_dll import prime_windows_gpu_dll_search_path

if TYPE_CHECKING:
    from llama_cpp import Llama  # type: ignore

log = logging.getLogger("jarvin.llmrt")

_CHAT_FORMAT_BY_LOGICAL: Dict[str, str] = {
    "phi-3-mini-4k-instruct": "chatml",
    "mistral-7b-instruct": "mistral-instruct",
    "neural-chat-7b": "llama-2",
    "qwen2.5-3b-instruct": "qwen",
    "llama-3.2-3b-instruct": "llama-3",
}


def _infer_chat_format(spec: GGUFModelSpec) -> Optional[str]:
    fmt = _CHAT_FORMAT_BY_LOGICAL.get(spec.logical_name)
    if fmt:
        return fmt
    fname = spec.filename.lower()
    if "phi-3" in fname or "phi3" in fname:
        return "chatml"
    if "mistral" in fname:
        return "mistral-instruct"
    if "qwen" in fname:
        return "qwen"
    if "llama-3" in fname or "llama3" in fname:
        return "llama-3"
    if "neural-chat" in fname:
        return "llama-2"
    return None


def _truthy(s: str | None) -> bool:
    if s is None:
        return False
    return s.strip().lower() in {"1", "true", "yes", "y", "on"}


def _capture_llama_system_info() -> Tuple[str | None, str | None]:
    """
    Best-effort capture of llama.cpp system/build info from llama-cpp-python.

    Returns (version_str, system_info_str). Either may be None.
    This is the most useful single log to prove whether CUDA/Metal/Vulkan backends exist.
    """
    try:
        prime_windows_gpu_dll_search_path()
        import llama_cpp  # type: ignore
    except Exception:
        return None, None

    version = getattr(llama_cpp, "__version__", None)

    # Preferred: llama_print_system_info() (prints; may exist depending on version)
    info: str | None = None
    if hasattr(llama_cpp, "llama_print_system_info"):
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                llama_cpp.llama_print_system_info()  # type: ignore[attr-defined]
            info = buf.getvalue().strip() or None
        except Exception:
            info = None

    # Fallback: llama_get_system_info() (returns string/bytes on some versions)
    if info is None and hasattr(llama_cpp, "llama_get_system_info"):
        try:
            raw = llama_cpp.llama_get_system_info()  # type: ignore[attr-defined]
            info = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
            info = info.strip() or None
        except Exception:
            info = None

    return version, info


def _guess_gpu_support_from_info(info: str | None) -> bool:
    """
    Heuristic only. If this says False, you almost certainly have a CPU-only build.
    """
    if not info:
        return False
    s = info.lower()
    # markers commonly present in system info when GPU backends are enabled
    markers = ("cuda", "metal", "vulkan", "opencl", "clblast", "hip", "sycl")
    return any(m in s for m in markers)


def _effective_llm_knobs() -> Tuple[int, Optional[int], int, bool, bool, bool]:
    """
    Return (n_ctx, n_threads, n_gpu_layers, verbose, log_system_info, require_gpu)
    honoring cfg.settings plus a few back-compat env overrides.
    """
    s = cfg.settings

    n_ctx = int(getattr(s, "llm_n_ctx", 4096) or 4096)
    n_threads: Optional[int] = getattr(s, "llm_n_threads", None)

    # Back-compat override
    n_threads_env = os.getenv("JARVIN_LLM_N_THREADS")
    if n_threads_env and n_threads_env.isdigit():
        n_threads = int(n_threads_env)

    n_gpu_layers = int(getattr(s, "llm_n_gpu_layers", 0) or 0)

    verbose = bool(getattr(s, "llm_verbose", False)) or _truthy(os.getenv("JARVIN_LLM_VERBOSE"))
    log_sys = bool(getattr(s, "llm_log_system_info", True))

    # Allow explicit env to disable logging if needed
    if os.getenv("JARVIN_LLM_LOG_SYSTEM_INFO") is not None:
        log_sys = _truthy(os.getenv("JARVIN_LLM_LOG_SYSTEM_INFO"))

    require_gpu = bool(getattr(s, "llm_require_gpu", False)) or _truthy(os.getenv("JARVIN_LLM_REQUIRE_GPU"))

    return n_ctx, n_threads, n_gpu_layers, verbose, log_sys, require_gpu


@lru_cache(maxsize=1)
def _load_llama() -> Optional["Llama"]:
    try:
        dll_dirs = prime_windows_gpu_dll_search_path()
        if dll_dirs:
            log.info("Primed Windows GPU DLL search path with %d director%s.", len(dll_dirs), "y" if len(dll_dirs) == 1 else "ies")

        from llama_cpp import Llama  # type: ignore
    except Exception as e:
        log.warning("llama-cpp-python could not be imported; local LLM disabled. %s", e)
        return None

    try:
        spec: GGUFModelSpec = pick_model()
        model_path = ensure_download(spec, models_dir=cfg.settings.models_dir)
        chat_format = _infer_chat_format(spec)

        n_ctx, n_threads, n_gpu_layers, verbose, log_sys, require_gpu = _effective_llm_knobs()

        # Log build/system info once at load (this is the key proof)
        llama_ver, sys_info = (None, None)
        gpu_supported_guess = False
        if log_sys:
            llama_ver, sys_info = _capture_llama_system_info()
            gpu_supported_guess = _guess_gpu_support_from_info(sys_info)

            if llama_ver:
                log.info("llama-cpp-python version=%s", llama_ver)
            if sys_info:
                # Keep it as a single log entry so it's easy to copy/paste.
                log.info("llama.cpp system info:\n%s", sys_info)

        # If user requested GPU offload, but build looks CPU-only, warn or fail
        wants_gpu = (n_gpu_layers != 0)
        if wants_gpu and not gpu_supported_guess:
            msg = (
                "GPU offload was requested (n_gpu_layers != 0) but llama.cpp system info does not "
                "indicate a GPU backend (CUDA/Metal/Vulkan/etc). This usually means you installed a CPU-only "
                "llama-cpp-python wheel, so the LLM will run on CPU."
            )
            if require_gpu:
                raise RuntimeError(msg)
            log.warning(msg)

        log.info(
            "🧠 Loading local LLM | path=%s chat_format=%s n_ctx=%d n_threads=%s n_gpu_layers=%d verbose=%s",
            model_path,
            chat_format or "default",
            n_ctx,
            str(n_threads) if n_threads is not None else "auto",
            n_gpu_layers,
            str(verbose),
        )

        # NOTE:
        # - verbose=True is the most direct runtime proof: llama.cpp prints offload lines like
        #   "offloading X layers to GPU" when GPU is actually used.
        llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=n_gpu_layers,
            chat_format=chat_format,
            verbose=verbose,
        )

        # Post-load confirmation log (best-effort; attributes vary by version)
        try:
            actual = getattr(llm, "n_gpu_layers", None)
            if actual is not None:
                log.info("LLM runtime reports n_gpu_layers=%s", str(actual))
        except Exception:
            pass

        return llm

    except Exception as e:
        log.exception("Failed to load local LLM: %s", e)
        return None


def ensure_llama_loaded() -> Optional["Llama"]:
    """
    Eagerly load the cached Llama instance.

    Safe to call multiple times; returns the shared instance or None
    if loading failed or llama-cpp-python is unavailable.
    """
    return _load_llama()


def chat_completion(
    system_prompt: str,
    user_text: str,
    temperature: float = 0.7,
    max_tokens: int = 256,
) -> Optional[str]:
    llm = _load_llama()
    if llm is None:
        return None

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_prompt.strip()},
        {"role": "user", "content": user_text.strip()},
    ]

    try:
        out = llm.create_chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=None,
        )
        return out["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.exception("LLM chat completion failed: %s", e)
        return None
