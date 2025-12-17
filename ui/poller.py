# ui/poller.py
from __future__ import annotations

from typing import Any, List, Tuple
import gradio as gr

from ui.api import (
    api_get_status, api_get_live, server_url,
    status_str, button_updates,
)


class Poller:
    """
    Encapsulates the UI polling state so the UI code in app.py stays small.

    Key behavior:
      - The timer NEVER touches chat_history, timestamps, or metrics HTML directly.
      - It only updates:
          * status banner
          * conversation_memory (when a NEW utterance appears)
          * start/stop buttons
          * TTS audio URL
          * live_seq (hidden seq state)
          * utter_ts_state / reply_ts_state (hidden)
          * metrics_state / metrics_seq (hidden)
      - `.change` handlers on live_seq and metrics_seq do the actual rendering.
    """

    def __init__(self) -> None:
        # status/banner
        self._last_banner: str | None = None

        # metrics edge detection (processing True -> False)
        self._last_processing: bool | None = None

        # audio
        self._last_tts_url: str | None = None

        # button state
        self._btn_state: dict[str, tuple[Any, Any, Any] | None] = {
            "start": None,
            "pause": None,
        }

        # last utterance sequence from backend (/live.seq) that actually
        # produced a NEW message in conversation_memory
        self._last_seq: int | None = None

        # last seen timestamps so we only update state when values change
        self._last_utter_ts: Any = None
        self._last_reply_ts: Any = None

        # metrics string + sequence id for metrics_seq
        self._last_metrics_val: str | None = None
        self._metrics_seq: int = 0

    @staticmethod
    def _norm_btn_state(u: dict) -> tuple[Any, Any, Any]:
        # gr.update(...) returns a dict-like; normalize to a comparable tuple
        return (u.get("interactive", None), u.get("visible", None), u.get("value", None))

    def _status_updates(self):
        """
        Fetch /status and /live and compute banner + button updates.
        Returns: (banner_out, start_btn_update, stop_btn_update, status_json, live_json)
        """
        s = api_get_status()
        l = api_get_live()

        # Banner
        banner_now = status_str(s, l) or "&nbsp;"
        if banner_now != self._last_banner:
            banner_out = banner_now
            self._last_banner = banner_now
        else:
            banner_out = gr.update()

        # Buttons
        listening = bool(s.get("listening", False))
        start_u_raw, pause_u_raw = button_updates(listening)

        start_tuple = self._norm_btn_state(start_u_raw)
        pause_tuple = self._norm_btn_state(pause_u_raw)

        if start_tuple != self._btn_state["start"]:
            start_u = start_u_raw
            self._btn_state["start"] = start_tuple
        else:
            start_u = gr.update()

        if pause_tuple != self._btn_state["pause"]:
            pause_u = pause_u_raw
            self._btn_state["pause"] = pause_tuple
        else:
            pause_u = gr.update()

        return banner_out, start_u, pause_u, s, l

    def tick(self, conversation_memory: list[tuple[str, str]] | None):
        """
        Gradio Timer callback.

        Inputs:
          - conversation_memory: current active conversation history
            (list[(role, message)]) from the State.

        Returns (matching outputs wired in app.py):
          - status_banner
          - conversation_memory (possibly updated, else gr.update())
          - start_btn
          - stop_btn
          - tts_audio
          - live_seq (int) – ONLY changes when a NEW message was appended
          - utter_ts_state – raw utterance timestamp (only when changed)
          - reply_ts_state – raw reply timestamp (only when changed)
          - metrics_state – metrics string (only when changed)
          - metrics_seq – int, only when metrics_state changes
        """
        try:
            banner_out, start_u, pause_u, s, l = self._status_updates()

            # Current values from /live
            t_now = (l.get("transcript") or "").strip()
            r_now = (l.get("reply") or "").strip()
            tts_rel = (l.get("tts_url") or "").strip()
            tts_abs = (server_url() + tts_rel) if tts_rel else ""

            # Sequence number from backend; advances once per utterance snapshot.
            seq_raw = l.get("seq")
            seq = seq_raw if isinstance(seq_raw, int) else None

            # Timestamps from backend (adapt keys if your JSON differs)
            utter_ts = l.get("utter_ts")   # e.g. utterance timestamp
            reply_ts = l.get("reply_ts")   # e.g. reply timestamp

            # Durations for metrics
            utt_ms = l.get("utter_ms")
            cyc_ms = l.get("cycle_ms")
            processing_now = bool(l.get("processing", False))

            # ---------- metrics_state / metrics_seq ----------
            metrics_state_out = gr.update()
            metrics_seq_out = gr.update()
            metrics_str: str | None = None

            # Edge detect processing True -> False to compute metrics once per cycle
            if self._last_processing is True and processing_now is False:
                parts: List[str] = []
                if utt_ms is not None:
                    parts.append(f"🎙️ utterance: {int(utt_ms)} ms")
                if cyc_ms is not None:
                    parts.append(f"⏱️ cycle: {int(cyc_ms)} ms")
                metrics_str = " | ".join(parts) if parts else "&nbsp;"

                if metrics_str != self._last_metrics_val:
                    self._last_metrics_val = metrics_str
                    self._metrics_seq += 1
                    metrics_state_out = metrics_str
                    metrics_seq_out = self._metrics_seq

            self._last_processing = processing_now

            # ---------- conversation history + live_seq ----------
            orig_hist: List[Tuple[str, str]] = list(conversation_memory or [])

            hist_out = gr.update()
            seq_out = gr.update()

            if seq is not None and (self._last_seq is None or seq > self._last_seq):
                new_hist: List[Tuple[str, str]] = list(orig_hist)
                mutated = False

                if t_now:
                    # Avoid duplicating the last pair by content (page-load / refresh safety).
                    tail = orig_hist[-2:]
                    duplicate = False
                    if len(tail) == 2:
                        last_user_role, last_user_msg = tail[0]
                        last_ass_role, last_ass_msg = tail[1]
                        if (
                            last_user_role == "user"
                            and last_user_msg == t_now
                            and last_ass_role == "assistant"
                            and (not r_now or last_ass_msg == r_now)
                        ):
                            duplicate = True

                    if not duplicate:
                        new_hist.append(("user", t_now))
                        if r_now:
                            new_hist.append(("assistant", r_now))
                        mutated = True

                # Always remember we've seen this seq, even if it gave no new text.
                self._last_seq = seq

                if mutated and new_hist != orig_hist:
                    hist_out = new_hist
                    # Only in this case do we bump live_seq so .change fires.
                    seq_out = seq

            # ---------- timestamp states ----------
            utter_state_out = gr.update()
            reply_state_out = gr.update()

            if utter_ts != self._last_utter_ts:
                self._last_utter_ts = utter_ts
                utter_state_out = utter_ts

            if reply_ts != self._last_reply_ts:
                self._last_reply_ts = reply_ts
                reply_state_out = reply_ts

            # ---------- TTS audio ----------
            audio_out = gr.update()
            if tts_abs and tts_abs != self._last_tts_url:
                audio_out = tts_abs
                self._last_tts_url = tts_abs

            return (
                banner_out,        # status_banner
                hist_out,          # conversation_memory
                start_u,           # start button
                pause_u,           # stop button
                audio_out,         # tts audio
                seq_out,           # live_seq (int)
                utter_state_out,   # utter_ts_state
                reply_state_out,   # reply_ts_state
                metrics_state_out, # metrics_state
                metrics_seq_out,   # metrics_seq
            )

        except Exception:
            # Never let the timer die — return "no changes" for all outputs.
            return (
                gr.update(),  # status_banner
                gr.update(),  # conversation_memory
                gr.update(),  # start button
                gr.update(),  # stop button
                gr.update(),  # tts audio
                gr.update(),  # live_seq
                gr.update(),  # utter_ts_state
                gr.update(),  # reply_ts_state
                gr.update(),  # metrics_state
                gr.update(),  # metrics_seq
            )
