# tests/backend/listener/test_intents.py
from __future__ import annotations

from backend.listener.intents import intent_shutdown, intent_confirm


def test_intent_shutdown_positive_examples():
    texts = [
        "please shut down the server",
        "can you power off",
        "stop listening now",
        "terminate the process",
        "kill the server",
    ]
    for t in texts:
        assert intent_shutdown(t) is True, f"expected shutdown intent for: {t!r}"


def test_intent_shutdown_respects_negations():
    texts = [
        "don't shut down yet",
        "do not power off",
        "not now, stop shutdown",
        "false alarm, do not quit",
    ]
    for t in texts:
        assert intent_shutdown(t) is False, f"expected NO shutdown for: {t!r}"


def test_intent_confirm_positive_examples():
    texts = [
        "confirm shutdown",
        "confirmed shutdown",
        "yes, shut down",
        "go ahead and exit",
    ]
    for t in texts:
        assert intent_confirm(t) is True, f"expected confirm intent for: {t!r}"


def test_intent_confirm_respects_negations():
    texts = [
        "don't confirm shutdown",
        "do not exit now",
        "not now, cancel it",
    ]
    for t in texts:
        assert intent_confirm(t) is False, f"expected NO confirm for: {t!r}"
