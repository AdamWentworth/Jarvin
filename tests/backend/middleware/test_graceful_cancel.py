import asyncio
import pytest

from backend.middleware.graceful_cancel import GracefulCancelMiddleware


class DummySend:
    async def __call__(self, message):
        pass


class DummyReceive:
    async def __call__(self):
        return {"type": "http.request"}


@pytest.mark.asyncio
async def test_middleware_passes_through():
    called = False

    async def app(scope, receive, send):
        nonlocal called
        called = True

    mw = GracefulCancelMiddleware(app)

    await mw({}, DummyReceive(), DummySend())

    assert called is True


@pytest.mark.asyncio
async def test_middleware_suppresses_cancelled_error():
    async def app(scope, receive, send):
        raise asyncio.CancelledError()

    mw = GracefulCancelMiddleware(app)

    # Should NOT raise CancelledError
    await mw({}, DummyReceive(), DummySend())


@pytest.mark.asyncio
async def test_middleware_does_not_suppress_other_exceptions():
    class CustomError(Exception):
        pass

    async def app(scope, receive, send):
        raise CustomError("boom")

    mw = GracefulCancelMiddleware(app)

    with pytest.raises(CustomError):
        await mw({}, DummyReceive(), DummySend())
