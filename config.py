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
  JARVIN_GRADIO_AUTO_OPEN=true
  JARVIN_GRADIO_OPEN_DELAY_SEC=1.0

  # NEW: persistence
  JARVIN_DATA_DIR=./data
  JARVIN_DB_FILENAME=jarvin.sqlite3
  JARVIN_DB_WAL=true
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

    # ---- Local LLM (llama.cpp) settings ----
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

    # ---- Server / Gradio UI ----
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    gradio_use_cdn: bool = True
    gradio_analytics_enabled: bool = False
    gradio_mount_path: str = "/ui"
    gradio_auto_open: bool = True
    gradio_open_delay_sec: float = 1.0

    # ---- Persistent data (NEW) ----
    data_dir: str = "data"
    db_filename: str = "jarvin.sqlite3"
    db_wal: bool = True  # enable WAL for safe concurrent reads/writes

    # pydantic-settings v2 config (replaces inner Config)
    model_config = SettingsConfigDict(
        env_prefix="JARVIN_",
        case_sensitive=False,
        extra="ignore",  # ignore stray envs to be safe
    )

    @property
    def db_path(self) -> str:
        # Resolve to absolute path and ensure folder exists when accessed
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
        """
        Accept None / "" → None, else enforce known sizes:
        tiny | base | small | medium | large
        """
        if v is None:
            return None
        vv = str(v).strip().lower()
        if vv in {"", "none", "auto"}:
            return None
        allowed = {"tiny", "base", "small", "medium", "large"}
        return vv if vv in allowed else "small"  # safe default


# Single global instance
settings = Settings()
