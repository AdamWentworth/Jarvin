from __future__ import annotations

import base64

import httpx
import pytest

import backend.api.app as app_mod
import backend.api.routes.transcription as transcription_mod
from backend.agent.voice.voice_transcription_review import VoiceTranscriptionReviewResult


@pytest.mark.asyncio
async def test_transcribe_bytes_route_accepts_base64_audio(monkeypatch, tmp_path):
    monkeypatch.setattr(app_mod.cfg.settings, "llm_auto_provision", False, raising=False)
    monkeypatch.setattr(app_mod.cfg.settings, "start_listener_on_boot", False, raising=False)
    monkeypatch.setattr(transcription_mod, "ensure_temp_dir", lambda: str(tmp_path))
    monkeypatch.setattr(transcription_mod, "transcribe_audio", lambda wav_path: f"ok:{wav_path.split('.')[-1]}")
    monkeypatch.setattr(
        transcription_mod,
        "review_remote_transcription",
        lambda text: VoiceTranscriptionReviewResult(
            confidence_level="high",
            confidence_score=0.91,
            action="accept",
            review_reason=f"reviewed:{text}",
        ),
    )

    payload = {
        "audio_base64": base64.b64encode(b"fake-audio").decode("ascii"),
        "content_type": "audio/webm",
        "filename": "clip.webm",
    }

    transport = httpx.ASGITransport(app=app_mod.create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/transcribe-bytes", json=payload)

    assert response.status_code == 200
    assert response.json() == {
        "transcribed_text": "ok:webm",
        "review": {
            "confidence_level": "high",
            "confidence_score": 0.91,
            "action": "accept",
            "suggested_text": None,
            "clarification_message": None,
            "review_reason": "reviewed:ok:webm",
        },
    }


@pytest.mark.asyncio
async def test_transcribe_bytes_route_rejects_invalid_base64(monkeypatch):
    monkeypatch.setattr(app_mod.cfg.settings, "llm_auto_provision", False, raising=False)
    monkeypatch.setattr(app_mod.cfg.settings, "start_listener_on_boot", False, raising=False)

    transport = httpx.ASGITransport(app=app_mod.create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/transcribe-bytes",
            json={
                "audio_base64": "not-base64",
                "content_type": "audio/webm",
                "filename": "clip.webm",
            },
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "invalid base64 audio payload"}


@pytest.mark.asyncio
async def test_transcribe_bytes_route_returns_500_for_transcription_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(app_mod.cfg.settings, "llm_auto_provision", False, raising=False)
    monkeypatch.setattr(app_mod.cfg.settings, "start_listener_on_boot", False, raising=False)
    monkeypatch.setattr(transcription_mod, "ensure_temp_dir", lambda: str(tmp_path))

    def _boom(_: str):
        raise RuntimeError("decoder exploded")

    monkeypatch.setattr(transcription_mod, "transcribe_audio", _boom)

    payload = {
        "audio_base64": base64.b64encode(b"fake-audio").decode("ascii"),
        "content_type": "audio/webm",
        "filename": "clip.webm",
    }

    transport = httpx.ASGITransport(app=app_mod.create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/transcribe-bytes", json=payload)

    assert response.status_code == 500
    assert response.json() == {"detail": "transcription failed: decoder exploded"}
