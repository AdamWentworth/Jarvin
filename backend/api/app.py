# backend/api/app.py
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
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
from backend.api.routes.llm import router as llm_router
from backend.api.routes.agent_tools import router as agent_tools_router
from backend.api.routes.workspace import router as workspace_router
from backend.api.routes.reminders import router as reminders_router
from backend.middleware.graceful_cancel import GracefulCancelMiddleware  # NEW
from backend.util.paths import ensure_temp_dir

log = logging.getLogger("jarvin")


def _desktop_shell_dist_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "clients" / "jarvin-ui" / "dist-host"


def _desktop_shell_not_built_response() -> PlainTextResponse:
    return PlainTextResponse(
        "Jarvin mobile/web shell is not built yet. Run `cd clients/jarvin-ui && npm run build:host` first.",
        status_code=503,
    )


def _desktop_shell_file_response(asset_path: str = ""):
    dist_root = _desktop_shell_dist_dir()
    if not dist_root.is_dir():
        return _desktop_shell_not_built_response()

    safe_root = dist_root.resolve()
    index_path = safe_root / "index.html"

    requested = asset_path.strip("/")
    if not requested:
        return FileResponse(index_path)

    candidate = (safe_root / requested).resolve()
    try:
        candidate.relative_to(safe_root)
    except ValueError:
        return PlainTextResponse("Not found.", status_code=404)

    if candidate.is_file():
        return FileResponse(candidate)

    # Let SPA-style routes fall back to index while real missing assets 404 cleanly.
    if "." in Path(requested).name:
        return PlainTextResponse("Not found.", status_code=404)

    return FileResponse(index_path)

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
    app.include_router(llm_router)
    app.include_router(agent_tools_router)
    app.include_router(workspace_router)
    app.include_router(reminders_router)

    @app.get("/", include_in_schema=False)
    def _root_redirect():
        return RedirectResponse(url="/app/", status_code=307)

    @app.get("/app", include_in_schema=False)
    def _desktop_shell_redirect():
        return RedirectResponse(url="/app/", status_code=307)

    @app.get("/app/", include_in_schema=False)
    def _desktop_shell_index():
        return _desktop_shell_file_response()

    @app.get("/app/{asset_path:path}", include_in_schema=False)
    def _desktop_shell_assets(asset_path: str):
        return _desktop_shell_file_response(asset_path)

    # Serve ephemeral files (ASR/utterances and synthesized TTS) under /_temp
    temp_root = ensure_temp_dir()
    app.mount("/_temp", StaticFiles(directory=temp_root, html=False), name="temp")

    return app
