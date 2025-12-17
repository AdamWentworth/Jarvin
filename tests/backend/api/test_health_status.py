# tests/backend/api/test_health_status.py
from __future__ import annotations

import types

import pytest

from backend.api.routes.health import healthz
from backend.api.routes.control import status as status_endpoint


class _DummyTask:
    def __init__(self, done: bool):
        self._done = done

    def done(self) -> bool:
        return self._done


class _DummyState:
    def __init__(self, listener_task):
        self.listener_task = listener_task


class _DummyApp:
    def __init__(self, listener_task):
        self.state = _DummyState(listener_task)


class _DummyRequest:
    def __init__(self, listener_task):
        self.app = _DummyApp(listener_task)


@pytest.mark.asyncio
async def test_healthz_reports_ok_when_idle():
    req = _DummyRequest(listener_task=None)
    resp = await healthz(req)
    assert resp["status"] == "ok"
    assert resp["listening"] is False


@pytest.mark.asyncio
async def test_healthz_reports_listening_when_task_running():
    req = _DummyRequest(listener_task=_DummyTask(done=False))
    resp = await healthz(req)
    assert resp["status"] == "ok"
    assert resp["listening"] is True


@pytest.mark.asyncio
async def test_status_endpoint_reflects_listener_task():
    # not running
    req = _DummyRequest(listener_task=None)
    resp = await status_endpoint(req)
    assert resp.listening is False

    # running
    req2 = _DummyRequest(listener_task=_DummyTask(done=False))
    resp2 = await status_endpoint(req2)
    assert resp2.listening is True
