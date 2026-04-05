# config.py
"""
Global configuration for Jarvin.

Usage (preferred):
    import config as cfg
    s = cfg.settings
    print(s.sample_rate)

Override via env vars (prefix JARVIN_, case-insensitive), e.g.:
  JARVIN_SAMPLE_RATE=44100
  JARVIN_LOG_LEVEL=debug
  JARVIN_CORS_ALLOW_ORIGINS='["http://localhost:3000"]'
  JARVIN_SERVER_HOST=0.0.0.0
  JARVIN_SERVER_PORT=8000

  # persistence
  JARVIN_DATA_DIR=./data
  JARVIN_DB_FILENAME=jarvin.sqlite3
  JARVIN_DB_WAL=true

  # LLM backend/runtime knobs
  JARVIN_LLM_BACKEND=llama_cpp
  JARVIN_OLLAMA_BASE_URL=http://127.0.0.1:11434
  JARVIN_OLLAMA_MODEL=
  JARVIN_OLLAMA_TIMEOUT_SEC=60
  JARVIN_LLM_N_CTX=4096
  JARVIN_LLM_N_THREADS=8
  JARVIN_LLM_N_GPU_LAYERS=-1

  # NEW: LLM diagnostics / GPU verification
  # If true, pass verbose=True to llama.cpp (prints offload info like "offloading X layers to GPU")
  JARVIN_LLM_VERBOSE=true
  # If true, capture and log llama.cpp "system info" at load (compile flags / backends)
  JARVIN_LLM_LOG_SYSTEM_INFO=true
  # If true, and GPU offload is requested but build looks CPU-only, fail hard at startup
  JARVIN_LLM_REQUIRE_GPU=false
"""
from __future__ import annotations

import os
from typing import List, Optional, Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["debug", "info", "warning", "error", "critical"]


class Settings(BaseSettings):
    # ---- Audio / capture ----
    sample_rate: int = 16_000
    chunk: int = 1024
    record_seconds: int = 5
    amp_factor: float = 10.0

    # Temp dir for ephemeral files (overwritten each cycle)
    temp_dir: str = "temp"

    # Whisper model selection
    # None -> auto-select based on GPU VRAM; otherwise "tiny"|"base"|"small"|"medium"|"large"
    whisper_model_size: Optional[str] = None

    # CORS (dev-friendly; restrict in prod). Supports JSON list via env.
    cors_allow_origins: List[str] = Field(default_factory=lambda: ["*"])

    # Logging
    log_level: LogLevel = "info"

    # When not persisting, delete the raw WAV after amplifying (saves I/O)
    delete_raw_after_amplify: bool = True

    # Listener / startup behavior
    initial_listener_delay: float = 0.2
    start_listener_on_boot: bool = True

    # Uvicorn reload behavior
    uvicorn_reload_windows: bool = False
    uvicorn_reload_others: bool = True

    # Uvicorn access logs (HTTP request lines)
    uvicorn_access_log: bool = False

    # ---- Local LLM settings ----
    models_dir: str = "models"
    llm_backend: str = "llama_cpp"
    llm_auto_provision: bool = True
    llm_force_logical_name: str = "phi-3-mini-4k-instruct"
    llm_model_preference: List[str] = Field(
        default_factory=lambda: [
            "mistral-7b-instruct",
            "phi-3-mini-4k-instruct",
            "neural-chat-7b",
        ]
    )
    llm_flat_layout: bool = True
    llm_clean_vendor_dirs: bool = True

    # Optional service backend (Jarvin keeps the UI; this is inference only)
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    ollama_timeout_sec: float = 60.0

    # llama.cpp runtime knobs
    llm_n_ctx: int = 4096
    llm_n_threads: Optional[int] = None
    llm_n_gpu_layers: int = -1

    # NEW: LLM diagnostics / GPU verification
    llm_verbose: bool = False
    llm_log_system_info: bool = True
    llm_require_gpu: bool = False

    # ---- Agent / local tools ----
    agent_tools_enabled: bool = True
    agent_workspace_root: str = "."
    agent_allow_file_writes: bool = True
    agent_allow_command_execution: bool = True
    agent_command_timeout_sec: float = 20.0
    agent_max_file_read_lines: int = 400
    agent_max_search_results: int = 100
    agent_web_search_provider: str = "duckduckgo_lite"
    google_search_api_key: str = ""
    google_search_engine_id: str = ""
    google_calendar_credentials_file: str = "secrets/google-calendar-client.json"
    google_calendar_token_file: str = "data/google-calendar-token.json"
    google_calendar_id: str = "primary"
    google_calendar_max_events: int = 10
    weather_temperature_unit: str = "fahrenheit"
    weather_wind_speed_unit: str = "mph"
    default_weather_location: str = ""

    # ---- Voice Activity / Noise Gate ----
    vad_calibration_sec: float = 1.5
    vad_threshold_mult: float = 3.0
    vad_threshold_abs: float = 200.0
    vad_attack_ms: int = 120
    vad_release_ms: int = 350
    vad_hangover_ms: int = 200
    vad_pre_roll_ms: int = 300
    vad_min_utterance_ms: int = 250
    vad_max_utterance_sec: float = 30
    normalize_to_dbfs: Optional[float] = -3.0

    # VAD logging
    vad_heartbeat_ms: int = 1000
    vad_log_transitions: bool = True
    vad_log_stats_every_n_frames: int = 0
    vad_log_threshold_changes_ms: int = 3000
    vad_tty_status: bool = True

    # VAD toggles
    vad_use_instant_rms_for_trigger: bool = True
    vad_floor_min: float = 20.0
    vad_floor_max: float = 4000.0
    vad_floor_adapt_margin: float = 0.90

    # Voice shutdown
    voice_shutdown_confirm: bool = False

    # ---- Server ----
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    # ---- Persistent data ----
    data_dir: str = "data"
    db_filename: str = "jarvin.sqlite3"
    db_wal: bool = True  # enable WAL for safe concurrent reads/writes

    # pydantic-settings v2 config
    model_config = SettingsConfigDict(
        env_prefix="JARVIN_",
        case_sensitive=False,
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @property
    def db_path(self) -> str:
        path = os.path.abspath(os.path.join(self.data_dir, self.db_filename))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    @field_validator("log_level", mode="before")
    @classmethod
    def _validate_log_level(cls, v: str) -> LogLevel:
        vv = str(v).lower().strip()
        return vv if vv in {"debug", "info", "warning", "error", "critical"} else "info"  # type: ignore[return-value]

    @field_validator("whisper_model_size", mode="before")
    @classmethod
    def _validate_whisper_size(cls, v: str | None) -> Optional[str]:
        if v is None:
            return None
        vv = str(v).strip().lower()
        if vv in {"", "none", "auto"}:
            return None
        allowed = {"tiny", "base", "small", "medium", "large"}
        return vv if vv in allowed else "small"

    @field_validator("llm_backend", mode="before")
    @classmethod
    def _validate_llm_backend(cls, v: str | None) -> str:
        vv = str(v or "").strip().lower()
        allowed = {"llama_cpp", "ollama_http"}
        return vv if vv in allowed else "llama_cpp"

    @field_validator("agent_web_search_provider", mode="before")
    @classmethod
    def _validate_agent_web_search_provider(cls, v: str | None) -> str:
        vv = str(v or "").strip().lower()
        allowed = {"duckduckgo_lite", "google_cse"}
        return vv if vv in allowed else "duckduckgo_lite"

    @field_validator("weather_temperature_unit", mode="before")
    @classmethod
    def _validate_weather_temperature_unit(cls, v: str | None) -> str:
        vv = str(v or "").strip().lower()
        allowed = {"celsius", "fahrenheit"}
        return vv if vv in allowed else "fahrenheit"

    @field_validator("weather_wind_speed_unit", mode="before")
    @classmethod
    def _validate_weather_wind_speed_unit(cls, v: str | None) -> str:
        vv = str(v or "").strip().lower()
        allowed = {"kmh", "ms", "mph", "kn"}
        return vv if vv in allowed else "mph"


# Single global instance
settings = Settings()
