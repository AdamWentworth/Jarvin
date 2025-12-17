# backend/api/routes/live.py
from __future__ import annotations

from fastapi import APIRouter
from backend.listener.live_state import get_snapshot

router = APIRouter(tags=["live"])

@router.get("/live")
async def live_latest() -> dict:
    return get_snapshot()
