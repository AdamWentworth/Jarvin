# ui/handlers.py
from __future__ import annotations

import logging
import time
from typing import List, Tuple
import gradio as gr

from ui.actions import (
    save_user_profile,
    clear_conversation_history,
    update_history_display,
    get_save_confirmation,
    # convo controls
    get_conversation_menu,
    activate_conversation,
    create_conversation,
    rename_active_conversation,
    delete_active_conversation,
)
from ui.api import (
    api_post_start,
    api_post_stop,
    api_post_shutdown,
    api_get_status,
    status_str,
    button_updates,
    api_get_audio_devices,
    api_post_audio_select,
)
from backend.listener.live_state import get_snapshot

log = logging.getLogger("jarvin.ui.audio")


def _short(s: str | None, n: int = 80) -> str:
    if not s:
        return ""
    return s if len(s) <= n else (s[: n - 1] + "…")


# ---------- Profile tab bindings ----------

def bind_profile_actions(components: dict) -> None:
    # Save profile
    components["save_btn"].click(
        fn=save_user_profile,
        inputs=[
            components["name"],
            components["goal"],
            components["mood"],
            components["communication_style"],
            components["response_length"],
        ],
        outputs=[components["user_context"]],
    ).then(fn=get_save_confirmation, outputs=[components["status"]])

    # ---- Mic device UI helpers ----
    def _present_from_data(data: dict):
        devices = data.get("devices", [])
        sel_idx = data.get("selected_index")
        sel_name = data.get("selected_name")
        choices = [f"[{d['index']}] {d['name']}" for d in devices]
        selected = f"[{sel_idx}] {sel_name}" if sel_idx is not None and sel_name else None
        label = (
            f"**Current input device:** `{sel_idx}` — **{sel_name}**"
            if sel_idx is not None and sel_name
            else "_No input device available_"
        )
        return choices, selected, label

    def _value_to_index(value: str | None) -> int | None:
        if not value:
            return None
        try:
            return int(value.split("]", 1)[0].strip("[ "))
        except Exception:
            return None

    def _load_devices_ui():
        t0 = time.perf_counter()
        data = api_get_audio_devices()
        choices, selected, label = _present_from_data(data)
        dt = (time.perf_counter() - t0) * 1000
        log.debug("UI load devices -> selected=%s | choices=%d | %.1f ms", _short(selected), len(choices), dt)
        return choices, selected, label

    def _refresh_devices():
        choices, selected, label = _load_devices_ui()
        return gr.update(choices=choices, value=selected), label

    def _apply_device(value: str | None):
        idx = _value_to_index(value)
        if idx is None:
            return gr.update(), "⚠️ Invalid selection."

        before = api_get_audio_devices()
        cur_idx = before.get("selected_index")
        cur_name = before.get("selected_name")
        if cur_idx is not None and idx == cur_idx:
            choices, selected, label = _present_from_data(before)
            return gr.update(choices=choices, value=selected), f"✅ Already using {label}"

        t0 = time.perf_counter()
        res = api_post_audio_select(idx, restart=True)
        if not res.get("ok", False):
            dt = (time.perf_counter() - t0) * 1000
            err = res.get("error", "unknown error")
            log.error("UI apply device failed in %.1f ms -> %s", dt, err)
            return gr.update(), f"❌ Failed to select device: {err}"

        after = api_get_audio_devices()
        choices, selected, label = _present_from_data(after)
        return gr.update(choices=choices, value=selected), f"✅ Switched to {label}"

    components["device_refresh_btn"].click(
        fn=_refresh_devices,
        outputs=[components["device_dropdown"], components["device_current"]],
        queue=False,
        show_progress=False,
    )
    components["device_dropdown"].change(
        fn=_apply_device,
        inputs=[components["device_dropdown"]],
        outputs=[components["device_dropdown"], components["device_current"]],
        show_progress=False,
    )

    components["_init_devices_fn"] = _refresh_devices


# ---------- Live tab bindings (conversation list + controls) ----------

def bind_live_actions(components: dict) -> None:
    # ---- Conversations panel wiring ----

    def _on_select_conversation(value):
        (choices, selected, subtitle), history = activate_conversation(value)
        return (
            gr.update(choices=choices, value=selected),  # conv_list
            subtitle,                                    # conv_status
            history,                                     # conversation_memory
            "",                                          # conv_error
        )

    def _on_new_conversation():
        (choices, selected, subtitle), history = create_conversation(None)
        return (
            gr.update(choices=choices, value=selected),
            subtitle,
            history,
            "",
        )

    def _on_rename_conversation(title):
        (choices, selected, subtitle) = rename_active_conversation(title)
        return (
            gr.update(choices=choices, value=selected),
            subtitle,
            "",
        )

    def _on_delete_conversation():
        (choices, selected, subtitle), history, error = delete_active_conversation()
        return (
            gr.update(choices=choices, value=selected),
            subtitle,
            history,
            error,
        )

    # Clear conversation -> wipe active convo only
    def _clear_all_conversation():
        history = clear_conversation_history()
        return history, ""

    # 3-dots menu visibility toggle
    def _toggle_conv_menu(open_state: bool | None):
        is_open = bool(open_state)
        new_open = not is_open
        return new_open, gr.update(visible=new_open)

    def _close_conv_menu():
        # Force menu closed, used by the "Close" button on the overlay
        return False, gr.update(visible=False)

    # Buttons (listener)
    def _start_listener():
        api_post_start()
        s = api_get_status()
        banner = status_str(s, get_snapshot()) or "&nbsp;"
        start_u, pause_u = button_updates(bool(s.get("listening", False)))
        return banner, start_u, pause_u

    def _stop_listener():
        api_post_stop()
        banner = '<span class="status-badge status-stopped">Stopped</span>'
        start_u, pause_u = button_updates(False)
        return banner, start_u, pause_u

    def _shutdown_server():
        api_post_shutdown()
        start_u, pause_u = button_updates(False, disable_all=True)
        return ('<span class="status-badge status-stopped">Shutting down…</span>', start_u, pause_u)

    # --- Wire conversation list and menu ---

    # Selecting a conversation from the list
    components["conv_list"].change(
        fn=_on_select_conversation,
        inputs=[components["conv_list"]],
        outputs=[
            components["conv_list"],
            components["conv_status"],
            components["conversation_memory"],
            components["conv_error"],
        ],
        show_progress=False,
    ).then(
        fn=update_history_display,
        inputs=[components["conversation_memory"]],
        outputs=[components["chat_history"]],
        show_progress=False,
    )

    # New chat button (no title input; rename handled via menu)
    components["new_conv_btn"].click(
        fn=_on_new_conversation,
        outputs=[
            components["conv_list"],
            components["conv_status"],
            components["conversation_memory"],
            components["conv_error"],
        ],
    ).then(
        fn=update_history_display,
        inputs=[components["conversation_memory"]],
        outputs=[components["chat_history"]],
    )

    # Toggle the conversation menu (⋯)
    components["conv_menu_btn"].click(
        fn=_toggle_conv_menu,
        inputs=[components["conv_menu_open_state"]],
        outputs=[components["conv_menu_open_state"], components["conv_menu_group"]],
        show_progress=False,
    )

    # Explicit close button inside the overlay
    components["conv_menu_close_btn"].click(
        fn=_close_conv_menu,
        outputs=[components["conv_menu_open_state"], components["conv_menu_group"]],
        show_progress=False,
    )

        # Rename current conversation, then close the menu
    components["rename_conv_btn"].click(
        fn=_on_rename_conversation,
        inputs=[components["rename_conv_title"]],
        outputs=[
            components["conv_list"],
            components["conv_status"],
            components["conv_error"],
        ],
    ).then(
        fn=_close_conv_menu,
        outputs=[components["conv_menu_open_state"], components["conv_menu_group"]],
        show_progress=False,
    )

        # Delete current conversation (blocked if it's the only one), then close the menu
    components["delete_conv_btn"].click(
        fn=_on_delete_conversation,
        outputs=[
            components["conv_list"],
            components["conv_status"],
            components["conversation_memory"],
            components["conv_error"],
        ],
    ).then(
        fn=update_history_display,
        inputs=[components["conversation_memory"]],
        outputs=[components["chat_history"]],
        show_progress=False,
    ).then(
        fn=_close_conv_menu,
        outputs=[components["conv_menu_open_state"], components["conv_menu_group"]],
        show_progress=False,
    )

    # Clear current active conversation history, then close the menu
    components["clear_conv_btn"].click(
        fn=_clear_all_conversation,
        outputs=[components["conversation_memory"], components["conv_error"]],
    ).then(
        fn=update_history_display,
        inputs=[components["conversation_memory"]],
        outputs=[components["chat_history"]],
        show_progress=False,
    ).then(
        fn=_close_conv_menu,
        outputs=[components["conv_menu_open_state"], components["conv_menu_group"]],
        show_progress=False,
    )

    # --- Start / Stop / Shutdown controls ---
    components["start_btn"].click(
        fn=_start_listener,
        outputs=[components["status_banner"], components["start_btn"], components["stop_btn"]],
        concurrency_limit=4,
    )
    components["stop_btn"].click(
        fn=_stop_listener,
        outputs=[components["status_banner"], components["start_btn"], components["stop_btn"]],
        concurrency_limit=4,
    )
    components["shutdown_btn"].click(
        fn=_shutdown_server,
        outputs=[components["status_banner"], components["start_btn"], components["stop_btn"]],
        concurrency_limit=2,
    )
