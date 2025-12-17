# backend/api/routes/health.py
from __future__ import annotations

import logging
from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])
log = logging.getLogger("jarvin.routes.health")


@router.get("/healthz")
async def healthz(request: Request) -> dict:
    """
    Lightweight liveness/readiness probe.
    Returns process-level 'ok' and whether the listener task is running.
    """
    app = request.app
    task = getattr(app.state, "listener_task", None)
    listening = task is not None and not task.done()
    return {
        "status": "ok",
        "listening": listening,
    }
