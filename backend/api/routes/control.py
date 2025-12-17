# backend/api/routes/control.py
from __future__ import annotations

import asyncio
import logging
import os
import sys
import threading
import time
from contextlib import suppress

from fastapi import APIRouter, Request

from backend.api.schemas import StatusResponse, SimpleMessage
from backend.listener.runner import run_listener

log = logging.getLogger("jarvin.routes.control")

router = APIRouter(tags=["control"])


@router.get("/status", response_model=StatusResponse)
async def status(request: Request) -> StatusResponse:
    app = request.app
    running = getattr(app.state, "listener_task", None) is not None and not app.state.listener_task.done()
    return StatusResponse(listening=running)


@router.post("/start", response_model=SimpleMessage)
async def start_listener(request: Request) -> SimpleMessage:
    app = request.app
    task = getattr(app.state, "listener_task", None)
    if task is not None and not task.done():
        return SimpleMessage(ok=True, message="Listener already running.")

    app.state.stop_event.clear()
    app.state.listener_task = asyncio.create_task(run_listener(app.state.stop_event, initial_delay=0.0))
    log.info("Listener started via control API.")
    return SimpleMessage(ok=True, message="Listener started.")


@router.post("/stop", response_model=SimpleMessage)
async def stop_listener(request: Request) -> SimpleMessage:
    app = request.app
    task = getattr(app.state, "listener_task", None)
    if task is None or task.done():
        return SimpleMessage(ok=True, message="Listener already stopped.")
    app.state.stop_event.set()
    log.info("Listener stop requested via control API.")
    return SimpleMessage(ok=True, message="Listener stopping...")


def _force_exit_soon(delay: float = 0.35) -> None:
    """
    Last-resort hard exit from a background thread after a small delay.
    Used mainly on Windows where graceful shutdown can sometimes hang.
    """
    def _worker():
        try:
            time.sleep(max(0.0, delay))
            os._exit(0)  # nosec - intentional hard exit as failsafe
        except Exception:
            # If even this fails, there's nothing else to do.
            pass
    threading.Thread(target=_worker, name="JarvinForceExit", daemon=True).start()


@router.post("/shutdown", response_model=SimpleMessage)
async def shutdown_server(request: Request) -> SimpleMessage:
    """
    Gracefully stop the listener and then ask Uvicorn to exit *after* this response is sent.
    Includes Windows failsafe (os._exit) if the Uvicorn handle is missing or unresponsive.
    """
    app = request.app

    # 1) Stop listener cleanly
    try:
        app.state.stop_event.set()
        task = getattr(app.state, "listener_task", None)
        if task and not task.done():
            with suppress(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=3.0)
    except Exception as e:
        log.warning("Error stopping listener during shutdown: %s", e)

    # 2) Ask Uvicorn to exit AFTER we finish returning 200 OK
    server = getattr(app.state, "uvicorn_server", None)

    async def _signal_exit():
        # Give the client a moment to fully receive the response
        await asyncio.sleep(0.15)
        if server is not None:
            log.info("Shutdown requested via control API. Signaling server exit…")
            server.should_exit = True
        else:
            # No handle to uvicorn; schedule a safe hard-exit fallback
            log.info("No uvicorn server handle; using hard-exit fallback.")
            _force_exit_soon(0.2)

        # Extra Windows robustness: if the process is still around shortly after, force exit.
        if sys.platform.startswith("win"):
            loop = asyncio.get_running_loop()
            loop.call_later(1.0, _force_exit_soon, 0.0)

    # IMPORTANT: actually schedule the coroutine on the running loop
    asyncio.create_task(_signal_exit())

    # 3) Respond immediately; UI can disable buttons and stop polling
    return SimpleMessage(ok=True, message="Server is shutting down…")
