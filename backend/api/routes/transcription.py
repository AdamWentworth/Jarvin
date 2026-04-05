from __future__ import annotations

import base64
import binascii
import logging
import mimetypes
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.api.schemas import TranscribeBytesRequest, TranscribeResponse
from backend.agent.voice.voice_transcription_review import review_remote_transcription
from backend.asr.whisper import transcribe_audio
from backend.util.paths import ensure_temp_dir

log = logging.getLogger("jarvin.routes.transcription")

router = APIRouter(tags=["transcription"])

MAX_BYTES = 50 * 1024 * 1024  # 50 MB


def _normalized_content_type(raw: str | None) -> str:
    return (raw or "").split(";", 1)[0].strip().lower()


def _supported_content_type_or_error(raw: str | None) -> str:
    ctype = _normalized_content_type(raw)
    if not (ctype.startswith("audio/") or ctype in {"", "application/octet-stream"}):
        raise HTTPException(status_code=400, detail=f"unsupported content type: {raw}")
    return ctype


def _temporary_audio_path(content_type: str, filename: str | None) -> str:
    suffix = ""
    if filename:
        candidate = Path(filename).suffix
        if candidate and len(candidate) <= 10:
            suffix = candidate

    if not suffix:
        suffix = mimetypes.guess_extension(content_type) or ".wav"

    root = ensure_temp_dir()
    return os.path.join(root, f"up_{uuid.uuid4().hex}{suffix}")


def _transcribe_bytes(filename: str | None, content_type: str | None, data: bytes) -> str:
    ctype = _supported_content_type_or_error(content_type)
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="empty upload")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail=f"file too large (> {MAX_BYTES // (1024 * 1024)} MB)")

    file_location = _temporary_audio_path(ctype, filename)

    with open(file_location, "wb") as handle:
        handle.write(data)

    log.info(
        "Received uploaded audio: %s (%s, %d bytes) -> %s",
        filename,
        content_type,
        len(data),
        file_location,
    )

    try:
        log.info("Running Whisper transcription for uploaded audio...")
        try:
            text = transcribe_audio(file_location)
        except HTTPException:
            raise
        except Exception as exc:
            log.exception("Uploaded audio transcription failed for %s", filename)
            raise HTTPException(status_code=500, detail=f"transcription failed: {exc}") from exc
        log.info("Uploaded audio transcription complete. Text length: %d", len(text))
        return text
    finally:
        try:
            os.remove(file_location)
        except Exception:
            pass


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_endpoint(audio_file: UploadFile = File(...)) -> TranscribeResponse:
    data = await audio_file.read()
    text = _transcribe_bytes(audio_file.filename, audio_file.content_type, data)
    review = review_remote_transcription(text)
    return TranscribeResponse(transcribed_text=text, review=review.to_payload())


@router.post("/transcribe-bytes", response_model=TranscribeResponse)
async def transcribe_bytes_endpoint(payload: TranscribeBytesRequest) -> TranscribeResponse:
    try:
        data = base64.b64decode(payload.audio_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid base64 audio payload") from exc

    text = _transcribe_bytes(payload.filename, payload.content_type, data)
    review = review_remote_transcription(text)
    return TranscribeResponse(transcribed_text=text, review=review.to_payload())
