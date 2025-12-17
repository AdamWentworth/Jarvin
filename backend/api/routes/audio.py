# backend/api/routes/audio.py
from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from audio.mic import (
    list_input_devices,
    get_default_input_device_index,
    set_default_input_device_index,
    set_selected_input_device as validate_and_select_device,
)
from backend.listener.runner import run_listener

log = logging.getLogger("jarvin.routes.audio")
router = APIRouter(tags=["audio"])


class DevicesResponse(BaseModel):
    devices: list[dict]
    selected_index: Optional[int]
    selected_name: Optional[str]


class SelectRequest(BaseModel):
    index: int
    restart: bool = True


class SelectResponse(BaseModel):
    ok: bool
    selected_index: Optional[int]
    selected_name: Optional[str]
    message: str | None = None


@router.get("/audio/devices", response_model=DevicesResponse)
async def get_devices() -> DevicesResponse:
    devs = list_input_devices()
    try:
        sel_idx = get_default_input_device_index()
    except Exception:
        sel_idx = None

    sel_name = None
    if sel_idx is not None:
        for i, n in devs:
            if i == sel_idx:
                sel_name = n
                break

    return DevicesResponse(
        devices=[{"index": i, "name": n} for i, n in devs],
        selected_index=sel_idx,
        selected_name=sel_name,
    )


@router.post("/audio/select", response_model=SelectResponse)
async def select_device(payload: SelectRequest, request: Request) -> SelectResponse:
    """
    Validate and select a new input device. Reject silent/virtual devices with a clear message.
    Optionally restart the listener to pick it up.
    """
    dev_map = dict(list_input_devices())
    name = dev_map.get(payload.index)

    if name is None:
        return SelectResponse(
            ok=False,
            selected_index=None,
            selected_name=None,
            message=f"Device index {payload.index} not found among input-capable devices.",
        )

    # 1) Validate by actually opening + probing the device (this also caches selection internally)
    try:
        idx, nm = validate_and_select_device(payload.index)
    except Exception as e:
        msg = str(e)
        log.warning("Mic select rejected: %s", msg)
        return SelectResponse(
            ok=False,
            selected_index=None,
            selected_name=None,
            message=(
                f"Could not use device [{payload.index}] {name}: {msg}. "
                "Pick a hardware microphone (not 'Sound Mapper') or enable the device in OS settings."
            ),
        )

    # 2) Cache as the default for subsequent opens
    try:
        set_default_input_device_index(idx, nm)
    except Exception:
        # Non-fatal: validation already succeeded and selection is cached in-process
        pass

    # 3) Optionally restart the listener so the new default is observed
    if payload.restart:
        app = request.app

        # stop if running
        task = getattr(app.state, "listener_task", None)
        if task is not None and not task.done():
            app.state.stop_event.set()
            log.info("Stopping listener to apply new input device…")
            try:
                # small timeout; if it overruns we'll just continue
                with asyncio.timeout(2.5):
                    with suppress(Exception):
                        await task
            except Exception:
                pass
            app.state.stop_event.clear()

        # start again with new default
        app.state.listener_task = asyncio.create_task(run_listener(app.state.stop_event, initial_delay=0.0))
        log.info("Listener restarted with input device [%d] %s", idx, nm or "")

    return SelectResponse(ok=True, selected_index=idx, selected_name=nm, message="Input device applied.")
