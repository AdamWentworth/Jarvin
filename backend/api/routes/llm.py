from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

import config as cfg
from backend.llm.model_manager import get_spec_by_logical_name, list_available_specs, pick_model
from backend.llm.runtime_llama_cpp import ensure_llama_loaded, reset_llama_runtime
from backend.llm.runtime_ollama import list_models as list_ollama_models
from backend.util.hw_detect import detect_hardware

log = logging.getLogger("jarvin.routes.llm")
router = APIRouter(tags=["llm"])


class Choice(BaseModel):
    label: str
    value: str


class LLMOptionsResponse(BaseModel):
    backend_choices: List[Choice]
    current_backend: str
    current_model: str
    local_model_choices: List[Choice]
    ollama_model_choices: List[Choice]
    ollama_available: bool
    ollama_error: str | None = None
    message: str | None = None


class LLMSelectRequest(BaseModel):
    backend: str
    model: str
    load_now: bool = True


def _backend_choices() -> List[Choice]:
    return [
        Choice(label="Embedded llama.cpp", value="llama_cpp"),
        Choice(label="Headless Ollama", value="ollama_http"),
    ]


def _local_model_choices() -> List[Choice]:
    profile = detect_hardware()
    out: List[Choice] = []
    for spec in list_available_specs(profile):
        label = f"{spec.logical_name} ({spec.quant}, ~{spec.mem_req_gb:.1f} GB)"
        out.append(Choice(label=label, value=spec.logical_name))
    return out


def _current_local_model() -> str:
    forced = str(cfg.settings.llm_force_logical_name or "").strip()
    if forced:
        return forced
    return pick_model().logical_name


def _ollama_choices_and_error() -> tuple[List[Choice], str | None]:
    try:
        models = list_ollama_models()
        return [Choice(label=name, value=name) for name in models], None
    except Exception as e:
        return [], str(e)


def _options_response(message: str | None = None) -> LLMOptionsResponse:
    backend = str(cfg.settings.llm_backend or "llama_cpp").strip().lower()
    local_choices = _local_model_choices()
    ollama_choices, ollama_error = _ollama_choices_and_error()

    if backend == "ollama_http":
        current_model = str(cfg.settings.ollama_model or "").strip()
    else:
        current_model = _current_local_model()

    return LLMOptionsResponse(
        backend_choices=_backend_choices(),
        current_backend=backend,
        current_model=current_model,
        local_model_choices=local_choices,
        ollama_model_choices=ollama_choices,
        ollama_available=ollama_error is None,
        ollama_error=ollama_error,
        message=message,
    )


@router.get("/llm/options", response_model=LLMOptionsResponse)
async def get_llm_options() -> LLMOptionsResponse:
    return _options_response()


@router.post("/llm/select", response_model=LLMOptionsResponse)
async def select_llm(payload: LLMSelectRequest) -> LLMOptionsResponse:
    backend = str(payload.backend or "").strip().lower()
    model = str(payload.model or "").strip()

    if backend not in {"llama_cpp", "ollama_http"}:
        return _options_response(message=f"Unsupported backend: {payload.backend}")

    if not model:
        return _options_response(message="Choose a model before applying settings.")

    cfg.settings.llm_backend = backend
    reset_llama_runtime()

    if backend == "llama_cpp":
        get_spec_by_logical_name(model)
        cfg.settings.llm_force_logical_name = model
        if payload.load_now:
            llm = ensure_llama_loaded()
            if llm is None:
                return _options_response(message=f"Failed to load local model: {model}")
        log.info("LLM settings updated | backend=%s model=%s", backend, model)
        return _options_response(message=f"Using embedded model: {model}")

    cfg.settings.ollama_model = model
    log.info("LLM settings updated | backend=%s model=%s", backend, model)
    return _options_response(message=f"Using headless Ollama model: {model}")
