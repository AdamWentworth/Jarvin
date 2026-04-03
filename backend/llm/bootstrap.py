from __future__ import annotations

import logging
import os  # kept from original, even if currently unused

import config as cfg
from backend.llm import runtime_ollama
from backend.llm.model_manager import GGUFModelSpec, ensure_download, pick_model
from backend.llm.runtime_llama_cpp import ensure_llama_loaded
from backend.util.hw_detect import detect_hardware

log = logging.getLogger("jarvin.llm")


async def provision_llm() -> str | None:
    s = cfg.settings
    if not s.llm_auto_provision:
        log.info("LLM auto-provision disabled.")
        return None

    try:
        backend = str(s.llm_backend or "llama_cpp").strip().lower()
        if backend == "ollama_http":
            info = runtime_ollama.probe_server()
            model = str(info.get("model") or "").strip()
            models = [str(m) for m in (info.get("models") or [])]

            log.info("Ollama server reachable | base_url=%s", info.get("base_url"))
            if not model:
                log.warning(
                    "Ollama backend selected but no model is configured via JARVIN_OLLAMA_MODEL."
                )
                return None

            if model not in models:
                log.warning(
                    "Configured Ollama model '%s' was not listed by the server. Jarvin will not auto-pull it; provision it yourself.",
                    model,
                )
            else:
                log.info("Ollama model ready | %s", model)
            return model

        profile = detect_hardware()
        log.info(
            "HW profile | os=%s arch=%s cpu_cores=%d ram=%.2fGB nvidia=%s vram=%sGB mps=%s",
            profile.os,
            profile.arch,
            profile.cpu_cores,
            profile.ram_gb,
            str(profile.has_nvidia),
            str(profile.vram_gb),
            str(profile.has_mps),
        )

        spec: GGUFModelSpec = pick_model(profile)
        log.info(
            "LLM spec selected | logical=%s repo=%s file=%s",
            spec.logical_name,
            spec.repo_id,
            spec.filename,
        )

        path = ensure_download(spec, models_dir=s.models_dir)
        log.info("LLM model ready | %s", path)

        llm = ensure_llama_loaded()
        if llm is not None:
            log.info("LLM runtime loaded eagerly at startup.")
        else:
            log.warning("LLM runtime not loaded; it will be initialized lazily on first use.")

        return path
    except Exception as e:
        log.exception("LLM provisioning failed: %s", e)
        return None
