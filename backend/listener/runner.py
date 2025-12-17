# backend/listener/runner.py
from __future__ import annotations

import asyncio
import logging
import time
import os
from typing import Optional

import config as cfg
from audio.mic import get_default_input_device_index
from backend.ai_engine import JarvinConfig
from backend.listener.intents import intent_shutdown, intent_confirm, CONFIRM_WINDOW_SEC
from backend.listener.live_state import set_snapshot, set_status
from backend.listener.loop import AudioLoop
from backend.core.pipeline import process_utterance
from backend.asr import WhisperASR

log = logging.getLogger("jarvin")

async def _watch_stop_event(stop_event: asyncio.Event, loop: AudioLoop) -> None:
    await stop_event.wait()
    try:
        loop.request_stop()
    except Exception:
        pass

async def run_listener(stop_event: asyncio.Event, initial_delay: float = 0.2) -> None:
    s = cfg.settings

    if initial_delay > 0:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=initial_delay)
            return
        except asyncio.TimeoutError:
            pass

    asr = WhisperASR(cfg.settings.whisper_model_size)
    try:
        dev = getattr(asr, "device", "cpu")
    except Exception:
        dev = "cpu"
    log.info("🧠 Whisper ready | device=%s", dev)

    try:
        device_index: Optional[int] = get_default_input_device_index()
    except Exception as e:
        log.exception("No input device available: %s", e)
        device_index = None

    cfg_ai = JarvinConfig()
    pending_shutdown_deadline: Optional[float] = None

    def _on_recording(flag: bool) -> None:
        set_status(recording=flag)

    audio = AudioLoop(
        sample_rate=s.sample_rate,
        chunk=s.chunk,
        device_index=device_index,
        on_recording=_on_recording,
    )
    stopper_task: Optional[asyncio.Task] = None

    try:
        set_status(recording=False, processing=False)
        with audio:
            stopper_task = asyncio.create_task(_watch_stop_event(stop_event, audio))

            log.info(
                "🎧 Microphone stream opened (chunk=%d, ~%dms/frame).",
                s.chunk,
                int((s.chunk / s.sample_rate) * 1000),
            )
            log.info("⚙️  Calibrating noise floor for %.1fs…", s.vad_calibration_sec)
            await asyncio.to_thread(audio.calibrate, s.vad_calibration_sec)

            utter_gen = audio.utterances()
            while not stop_event.is_set():
                cycle_t0 = time.perf_counter()
                try:
                    pcm, sr = await asyncio.to_thread(next, utter_gen)
                except StopIteration:
                    return
                except Exception as e:
                    if stop_event.is_set():
                        return
                    log.exception("VAD stream error: %s", e)
                    await asyncio.sleep(0.05)
                    continue

                set_status(processing=True)

                text, reply, tms, wav_path, tts_wav_path = await asyncio.to_thread(
                    process_utterance,
                    pcm,
                    sr,
                    cfg_ai=cfg_ai,
                    asr=asr,
                )

                # Voice shutdown logic (no hard os._exit; just stop listener)
                if not s.voice_shutdown_confirm:
                    if text and intent_shutdown(text):
                        log.info("🛑 Voice shutdown requested. Stopping listener…")
                        set_status(processing=False)
                        stop_event.set()
                        return
                else:
                    now = time.monotonic()
                    if pending_shutdown_deadline and now > pending_shutdown_deadline:
                        pending_shutdown_deadline = None
                    if pending_shutdown_deadline is None:
                        if text and intent_shutdown(text):
                            pending_shutdown_deadline = now + CONFIRM_WINDOW_SEC
                            log.info(
                                "⚠️  Shutdown intent detected. Waiting up to %.0fs for confirmation.",
                                CONFIRM_WINDOW_SEC,
                            )
                            set_snapshot(
                                transcript=text,
                                reply="To confirm shutdown, say: 'confirm shutdown'.",
                                cycle_ms=None,
                                utter_ms=tms.get("utter_ms"),
                                wav_path=wav_path,
                                tts_url=None,
                            )
                            set_status(processing=False)
                            try:
                                await asyncio.wait_for(stop_event.wait(), timeout=0.05)
                            except asyncio.TimeoutError:
                                pass
                            continue
                    else:
                        if text and intent_confirm(text):
                            log.info("🛑 Voice confirmation received. Stopping listener…")
                            set_status(processing=False)
                            stop_event.set()
                            return

                cycle_ms = int((time.perf_counter() - cycle_t0) * 1000)
                if text:
                    log.info("📝  [result] “%s” (ASR %d ms)", text, tms.get("transcribe_ms", 0))
                else:
                    log.info("📝  [result] (empty) in %d ms", tms.get("transcribe_ms", 0))

                if reply:
                    log.info("📣  [reply] %s", reply)
                log.info("⏱️  [cycle] done in %d ms\n", cycle_ms)

                # NOTE: Turns are already persisted inside process_utterance().
                #       Do NOT append again here (that caused duplicate history).

                tts_url = f"/_temp/{os.path.basename(tts_wav_path)}" if tts_wav_path else None
                set_snapshot(
                    transcript=text if text else None,
                    reply=reply if reply else None,
                    cycle_ms=cycle_ms,
                    utter_ms=tms.get("utter_ms"),
                    wav_path=wav_path,
                    tts_url=tts_url,
                )

                set_status(processing=False)

                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=0.05)
                except asyncio.TimeoutError:
                    pass

    except asyncio.CancelledError:
        return
    finally:
        try:
            if stopper_task:
                stopper_task.cancel()
        except Exception:
            pass
        set_status(recording=False, processing=False)
