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
        response_started = False
        response_complete = False

        async def tracked_send(message):
            nonlocal response_started, response_complete
            message_type = message.get("type")
            if message_type == "http.response.start":
                response_started = True
            elif message_type == "http.response.body" and not message.get("more_body", False):
                response_complete = True
            await send(message)

        try:
            await self.app(scope, receive, tracked_send)
        except asyncio.CancelledError:
            if scope.get("type") == "http" and response_started and not response_complete:
                raise
            return
