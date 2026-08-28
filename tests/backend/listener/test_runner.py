from __future__ import annotations

import asyncio

import pytest

from backend.listener import runner


@pytest.mark.asyncio
async def test_exhausted_utterance_iterator_does_not_raise_stop_iteration_into_future():
    result = await asyncio.to_thread(runner._next_utterance_or_end, iter(()))

    assert result is runner._UTTERANCE_END


def test_next_utterance_returns_audio_tuple():
    expected = (b"pcm", 16_000)

    assert runner._next_utterance_or_end(iter((expected,))) == expected
