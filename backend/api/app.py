# backend/api/app.py
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import config as cfg
from backend.listener.runner import run_listener
from backend.llm.bootstrap import provision_llm
from backend.api.routes.transcription import router as transcription_router
from backend.api.routes.control import router as control_router
from backend.api.routes.health import router as health_router
from backend.api.routes.chat import router as chat_router
from backend.api.routes.live import router as live_router
from backend.api.routes.audio import router as audio_router  # <-- single audio router
from backend.middleware.graceful_cancel import GracefulCancelMiddleware  # NEW
from backend.util.paths import ensure_temp_dir

log = logging.getLogger("jarvin")

@asynccontextmanager
async def _lifespan(app: FastAPI):
    s = cfg.settings
    app.state.stop_event = asyncio.Event()

    if s.llm_auto_provision:
        try:
            await provision_llm()
        except Exception as e:
            log.exception("LLM provisioning failed: %s", e)

    app.state.listener_task = None
    if s.start_listener_on_boot:
        app.state.listener_task = asyncio.create_task(
            run_listener(app.state.stop_event, initial_listener_delay := s.initial_listener_delay)
        )
        log.info("🎧 Listener task started automatically on server boot.")
    else:
        log.info("🟡 start_listener_on_boot is False — server starts deaf; use /start to begin listening.")

    try:
        yield
    except (asyncio.CancelledError, KeyboardInterrupt):
        log.debug("Lifespan cancellation received during shutdown; suppressing exception.")
    except Exception as e:
        log.exception("Unhandled exception in lifespan: %s", e)
    finally:
        log.info("🛑 Shutting down listener…")
        app.state.stop_event.set()
        task = getattr(app.state, "listener_task", None)
        if task:
            with suppress(asyncio.CancelledError):
                await task
        log.info("✅ Listener stopped.")

def create_app() -> FastAPI:
    s = cfg.settings
    app = FastAPI(title="Jarvin Local", lifespan=_lifespan)

    # Swallow benign cancellations while shutting down (prevents noisy stack traces)
    app.add_middleware(GracefulCancelMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(transcription_router)
    app.include_router(control_router)
    app.include_router(chat_router)
    app.include_router(live_router)
    app.include_router(audio_router)  # <-- single include

    # Serve ephemeral files (ASR/utterances and synthesized TTS) under /_temp
    temp_root = ensure_temp_dir()
    app.mount("/_temp", StaticFiles(directory=temp_root, html=False), name="temp")

    return app
