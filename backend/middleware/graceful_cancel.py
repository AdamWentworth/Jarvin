# backend/middleware/graceful_cancel.py
from __future__ import annotations

import asyncio
from starlette.types import ASGIApp, Scope, Receive, Send

class GracefulCancelMiddleware:
    """
    Suppresses asyncio.CancelledError that bubble up during shutdown/connection drops.
    This avoids noisy 'ERROR: Exception in ASGI application' logs on graceful exit.
    """
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await self.app(scope, receive, send)
        except asyncio.CancelledError:
            # Ignore cancellations (typical on shutdown or client disconnect)
            return
