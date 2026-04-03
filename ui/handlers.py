from __future__ import annotations

import logging
import time

import gradio as gr

from backend.ai_engine import mode_hint, mode_label, normalize_mode
from backend.listener.live_state import get_snapshot
from memory.conversation import get_conversation_history
from ui.actions import (
    activate_conversation,
    clear_conversation_history,
    create_conversation,
    delete_active_conversation,
    format_active_conversation,
    get_conversation_menu,
    get_save_confirmation,
    rename_active_conversation,
    save_user_profile,
    update_history_display,
)
from ui.api import (
    api_get_audio_devices,
    api_get_llm_options,
    api_get_status,
    api_post_audio_select,
    api_post_chat,
    api_post_llm_select,
    api_post_shutdown,
    api_post_start,
    api_post_stop,
    button_updates,
    status_str,
)

log = logging.getLogger("jarvin.ui")


def _short(s: str | None, n: int = 80) -> str:
    if not s:
        return ""
    return s if len(s) <= n else (s[: n - 3] + "...")


def bind_profile_actions(components: dict) -> None:
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

    def _present_from_data(data: dict):
        devices = data.get("devices", [])
        sel_idx = data.get("selected_index")
        sel_name = data.get("selected_name")
        choices = [f"[{d['index']}] {d['name']}" for d in devices]
        selected = f"[{sel_idx}] {sel_name}" if sel_idx is not None and sel_name else None
        label = (
            f"**Current input device:** `{sel_idx}` - **{sel_name}**"
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
            return gr.update(), "Invalid selection."

        before = api_get_audio_devices()
        cur_idx = before.get("selected_index")
        cur_name = before.get("selected_name")
        if cur_idx is not None and idx == cur_idx:
            choices, selected, label = _present_from_data(before)
            return gr.update(choices=choices, value=selected), f"Already using {label}"

        t0 = time.perf_counter()
        res = api_post_audio_select(idx, restart=True)
        if not res.get("ok", False):
            dt = (time.perf_counter() - t0) * 1000
            err = res.get("error", "unknown error")
            log.error("UI apply device failed in %.1f ms -> %s", dt, err)
            return gr.update(), f"Failed to select device: {err}"

        after = api_get_audio_devices()
        choices, selected, label = _present_from_data(after)
        return gr.update(choices=choices, value=selected), f"Switched to {label}"

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


def bind_live_actions(components: dict) -> None:
    def _conversation_heading(selected: str | None) -> str:
        return format_active_conversation(selected)

    def _choice_tuples(items: list[dict]) -> list[tuple[str, str]]:
        return [(str(item.get("label") or item.get("value") or ""), str(item.get("value") or "")) for item in items]

    def _model_choices_for_backend(options: dict, backend: str | None) -> list[tuple[str, str]]:
        selected_backend = str(backend or "").strip().lower()
        key = "ollama_model_choices" if selected_backend == "ollama_http" else "local_model_choices"
        return _choice_tuples(list(options.get(key) or []))

    def _selected_model_for_backend(options: dict, backend: str | None) -> str | None:
        selected_backend = str(backend or "").strip().lower()
        current_backend = str(options.get("current_backend") or "").strip().lower()
        current_model = str(options.get("current_model") or "").strip()
        if selected_backend == current_backend and current_model:
            return current_model
        choices = _model_choices_for_backend(options, selected_backend)
        return choices[0][1] if choices else None

    def _render_llm_options(options: dict, *, selected_backend: str | None = None):
        backend_value = str(selected_backend or options.get("current_backend") or "llama_cpp").strip().lower()
        backend_choices = _choice_tuples(list(options.get("backend_choices") or []))
        model_choices = _model_choices_for_backend(options, backend_value)
        model_value = _selected_model_for_backend(options, backend_value)
        status_bits: list[str] = []
        if model_value:
            backend_label = "Embedded llama.cpp" if backend_value == "llama_cpp" else "Headless Ollama"
            status_bits.append(f"Current engine: **{backend_label}**  |  Model: `{model_value}`")
        message = str(options.get("message") or "").strip()
        if message:
            status_bits.append(message)
        ollama_error = str(options.get("ollama_error") or "").strip()
        if ollama_error and backend_value == "ollama_http":
            status_bits.append(f"Ollama note: {ollama_error}")
        status_text = "  \n".join(status_bits) if status_bits else "&nbsp;"
        return (
            options,
            gr.update(choices=backend_choices, value=backend_value),
            gr.update(choices=model_choices, value=model_value),
            status_text,
        )

    def _refresh_llm_settings():
        options = api_get_llm_options()
        return _render_llm_options(options)

    def _on_backend_change(selected_backend: str | None, options: dict | None):
        opts = dict(options or {})
        if not opts:
            opts = api_get_llm_options()
        _, _, model_update, status_text = _render_llm_options(opts, selected_backend=selected_backend)
        return model_update, status_text

    def _apply_llm_settings(backend: str | None, model: str | None):
        chosen_backend = str(backend or "").strip().lower()
        chosen_model = str(model or "").strip()
        if not chosen_backend or not chosen_model:
            return gr.update(), gr.update(), gr.update(), "Choose a backend and model first."
        options = api_post_llm_select(chosen_backend, chosen_model, load_now=True)
        _, backend_update, model_update, status_text = _render_llm_options(options)
        return options, backend_update, model_update, status_text

    def _on_select_conversation(value):
        (choices, selected, subtitle), history = activate_conversation(value)
        return (
            gr.update(choices=choices, value=selected),
            _conversation_heading(selected),
            history,
            "",
        )

    def _on_new_conversation():
        (choices, selected, subtitle), history = create_conversation(None)
        return (
            gr.update(choices=choices, value=selected),
            _conversation_heading(selected),
            history,
            "",
        )

    def _on_rename_conversation(title):
        choices, selected, subtitle = rename_active_conversation(title)
        return (
            gr.update(choices=choices, value=selected),
            _conversation_heading(selected),
            "",
        )

    def _on_delete_conversation():
        (choices, selected, subtitle), history, error = delete_active_conversation()
        return (
            gr.update(choices=choices, value=selected),
            _conversation_heading(selected),
            history,
            error,
        )

    def _clear_all_conversation():
        history = clear_conversation_history()
        return history, ""

    def _close_conv_menu_on_success(error: str | None):
        keep_open = bool((error or "").strip())
        return keep_open, gr.update(visible=keep_open)

    def _toggle_conv_menu(open_state: bool | None):
        new_open = not bool(open_state)
        return new_open, gr.update(visible=new_open)

    def _close_conv_menu():
        return False, gr.update(visible=False)

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
        return '<span class="status-badge status-stopped">Shutting down...</span>', start_u, pause_u

    def _update_chat_mode_hint(mode: str | None):
        return mode_hint(mode)

    def _begin_typed_chat(user_text: str | None, mode: str | None):
        text = (user_text or "").strip()
        if not text:
            return "Type a message to Jarvin first.", gr.update(interactive=True)
        return f"Thinking in **{mode_label(mode)}**...", gr.update(interactive=False)

    def _send_typed_chat(user_text: str | None, mode: str | None):
        text = (user_text or "").strip()
        if not text:
            return (
                gr.update(),
                gr.update(),
                user_text or "",
                "Type a message to Jarvin first.",
                gr.update(interactive=True),
            )

        normalized_mode = normalize_mode(mode)
        try:
            result = api_post_chat(text, mode=normalized_mode)
            history = get_conversation_history()
            used_mode = normalize_mode(result.get("mode_used"))
            return (
                history,
                update_history_display(history),
                "",
                f"Reply ready in **{mode_label(used_mode)}** mode.",
                gr.update(interactive=True),
            )
        except Exception as e:
            return (
                gr.update(),
                gr.update(),
                user_text or "",
                f"Chat failed: {e}",
                gr.update(interactive=True),
            )

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

    components["conv_menu_btn"].click(
        fn=_toggle_conv_menu,
        inputs=[components["conv_menu_open_state"]],
        outputs=[components["conv_menu_open_state"], components["conv_menu_group"]],
        show_progress=False,
    )

    components["conv_menu_close_btn"].click(
        fn=_close_conv_menu,
        outputs=[components["conv_menu_open_state"], components["conv_menu_group"]],
        show_progress=False,
    )

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
        fn=_close_conv_menu_on_success,
        inputs=[components["conv_error"]],
        outputs=[components["conv_menu_open_state"], components["conv_menu_group"]],
        show_progress=False,
    )

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

    components["chat_mode"].change(
        fn=_update_chat_mode_hint,
        inputs=[components["chat_mode"]],
        outputs=[components["chat_mode_hint"]],
        show_progress=False,
    )

    components["llm_refresh_btn"].click(
        fn=_refresh_llm_settings,
        outputs=[
            components["llm_options_state"],
            components["llm_backend"],
            components["llm_model"],
            components["llm_status"],
        ],
        show_progress=False,
    )

    components["llm_backend"].change(
        fn=_on_backend_change,
        inputs=[components["llm_backend"], components["llm_options_state"]],
        outputs=[components["llm_model"], components["llm_status"]],
        show_progress=False,
    )

    components["llm_apply_btn"].click(
        fn=_apply_llm_settings,
        inputs=[components["llm_backend"], components["llm_model"]],
        outputs=[
            components["llm_options_state"],
            components["llm_backend"],
            components["llm_model"],
            components["llm_status"],
        ],
        show_progress=False,
    )

    components["chat_send_btn"].click(
        fn=_begin_typed_chat,
        inputs=[components["chat_input"], components["chat_mode"]],
        outputs=[components["chat_status"], components["chat_send_btn"]],
        show_progress=False,
    ).then(
        fn=_send_typed_chat,
        inputs=[components["chat_input"], components["chat_mode"]],
        outputs=[
            components["conversation_memory"],
            components["chat_history"],
            components["chat_input"],
            components["chat_status"],
            components["chat_send_btn"],
        ],
        show_progress=False,
    )

    components["_init_llm_fn"] = _refresh_llm_settings

    components["chat_input"].submit(
        fn=_begin_typed_chat,
        inputs=[components["chat_input"], components["chat_mode"]],
        outputs=[components["chat_status"], components["chat_send_btn"]],
        show_progress=False,
    ).then(
        fn=_send_typed_chat,
        inputs=[components["chat_input"], components["chat_mode"]],
        outputs=[
            components["conversation_memory"],
            components["chat_history"],
            components["chat_input"],
            components["chat_status"],
            components["chat_send_btn"],
        ],
        show_progress=False,
    )
