# backend/api/routes/live.py
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.listener.live_state import get_snapshot, wait_next

router = APIRouter(tags=["live"])


@router.get("/live")
async def live_latest() -> dict:
    return get_snapshot()


@router.get("/live/stream")
async def live_stream(request: Request) -> StreamingResponse:
    async def event_generator():
        snapshot = get_snapshot()
        last_rev = snapshot.get("rev")
        yield _format_sse(snapshot)

        while True:
            if await request.is_disconnected():
                break

            next_snapshot = await asyncio.to_thread(wait_next, last_rev, 20.0)
            next_rev = next_snapshot.get("rev")
            if next_rev == last_rev:
                yield ": keep-alive\n\n"
                continue

            last_rev = next_rev
            yield _format_sse(next_snapshot)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


def _format_sse(snapshot: dict) -> str:
    event_id = snapshot.get("rev")
    payload = json.dumps(snapshot, ensure_ascii=True)
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append("event: live")
    lines.append(f"data: {payload}")
    return "\n".join(lines) + "\n\n"
