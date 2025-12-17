# backend/api/routes/transcription.py
from __future__ import annotations

import os
import uuid
import mimetypes
import logging

from fastapi import APIRouter, UploadFile, File

import config as cfg
from backend.asr.whisper import transcribe_audio
from backend.api.schemas import (
    TranscribeResponse,
    ErrorResponse,
 )
from backend.util.paths import ensure_temp_dir

log = logging.getLogger("jarvin.routes.transcription")

router = APIRouter(tags=["transcription"])

@router.post("/transcribe", response_model=TranscribeResponse | ErrorResponse)
async def transcribe_endpoint(audio_file: UploadFile = File(...)) -> TranscribeResponse | ErrorResponse:
    ctype = (audio_file.content_type or "").lower()
    if not (ctype.startswith("audio/") or ctype in {"", "application/octet-stream"}):
        return ErrorResponse(error=f"unsupported content type: {audio_file.content_type}")

    guessed_ext = mimetypes.guess_extension(ctype) or ".wav"

    root = ensure_temp_dir()
    file_location = os.path.join(root, f"up_{uuid.uuid4().hex}{guessed_ext}")

    MAX_BYTES = 50 * 1024 * 1024  # 50 MB
    data = await audio_file.read()
    if len(data) == 0:
        return ErrorResponse(error="empty upload")
    if len(data) > MAX_BYTES:
        return ErrorResponse(error=f"file too large (> {MAX_BYTES // (1024*1024)} MB)")

    with open(file_location, "wb") as f:
        f.write(data)

    log.info(
        "📥 Received file: %s (%s, %d bytes) → %s",
        audio_file.filename,
        audio_file.content_type,
        len(data),
        file_location,
    )

    try:
        log.info("🧠 Running Whisper transcription (one-off)…")
        text = transcribe_audio(file_location)
        log.info("✅ Done. Text length: %d", len(text))
        return TranscribeResponse(transcribed_text=text)
    finally:
        try:
            os.remove(file_location)
        except Exception:
            pass
