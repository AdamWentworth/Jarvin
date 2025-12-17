# ui/app.py
from __future__ import annotations

import gradio as gr

from ui.styles import CSS
from ui.components import build_header, build_profile_tab, build_live_tab, init_state
from ui.handlers import bind_profile_actions, bind_live_actions
from ui.actions import update_history_display, load_user_profile_fields, get_conversation_menu
from ui.poller import Poller
from memory.conversation import get_conversation_history


def create_app():
    with gr.Blocks(css=CSS) as demo:
        components: dict[str, gr.Component] = {}
        init_state(components)

        build_header()
        with gr.Tabs():
            build_profile_tab(components)
            build_live_tab(components)

        # Wire actions for Profile + Live
        bind_profile_actions(components)
        bind_live_actions(components)

        # --- Single page-load initializer (devices + saved profile + conversations + chat log) ---
        def _init_page():
            # 1) Device UI (choices + selected + label)
            choices_update, label = components["_init_devices_fn"]()  # returns (Dropdown.update, label)

            # 2) Saved profile prefill
            name, goal, mood, style, length, status = load_user_profile_fields()

            # 3) Conversations list (radio) with active on top
            conv_choices, conv_selected, conv_subtitle = get_conversation_menu()

            # 4) Active conversation history -> state + rendered chat log
            history = get_conversation_history()
            chat_html = update_history_display(history)

            return (
                choices_update,   # device dropdown update (choices + selected)
                label,            # device_current Markdown
                name, goal, mood, style, length, status,  # profile fields + status text
                gr.update(choices=conv_choices, value=conv_selected),  # conversations radio
                conv_subtitle,    # conv_status
                history,          # conversation_memory state
                chat_html,        # chat_history Chatbot
            )

        demo.load(
            fn=_init_page,
            outputs=[
                components["device_dropdown"],
                components["device_current"],
                components["name"],
                components["goal"],
                components["mood"],
                components["communication_style"],
                components["response_length"],
                components["status"],
                components["conv_list"],
                components["conv_status"],
                components["conversation_memory"],
                components["chat_history"],
            ],
            show_progress=False,
        )

        # ✅ Single polling loop: DOES NOT touch chat_history, timestamps, or metrics HTML directly.
        poller = Poller()
        timer = gr.Timer(value=0.75, active=True)  # 750ms
        timer.tick(
            fn=poller.tick,
            inputs=[components["conversation_memory"]],
            outputs=[
                components["status_banner"],        # status banner
                components["conversation_memory"],  # updated history
                components["start_btn"],            # start button state
                components["stop_btn"],             # stop button state
                components["tts_audio"],            # TTS audio URL
                components["live_seq"],             # hidden seq state
                components["utter_ts_state"],       # hidden utterance timestamp
                components["reply_ts_state"],       # hidden reply timestamp
                components["metrics_state"],        # hidden metrics text
                components["metrics_seq"],          # hidden metrics seq
            ],
            show_progress=False,
            concurrency_limit=1,
        )

        # Helper: render chat + timestamps when live_seq changes (NEW utterance only)
        def _render_history_and_timestamps(history, utter_ts_state, reply_ts_state):
            chat_html = update_history_display(history)

            if utter_ts_state is None:
                utter_label = "&nbsp;"
            else:
                utter_label = f"Utterance: {utter_ts_state}"

            if reply_ts_state is None:
                reply_label = "&nbsp;"
            else:
                reply_label = f"Response: {reply_ts_state}"

            return chat_html, utter_label, reply_label

        # Chat + timestamps re-render ONLY when live_seq changes
        components["live_seq"].change(
            fn=_render_history_and_timestamps,
            inputs=[
                components["conversation_memory"],
                components["utter_ts_state"],
                components["reply_ts_state"],
            ],
            outputs=[
                components["chat_history"],
                components["utter_ts_md"],
                components["reply_ts_md"],
            ],
            show_progress=False,
        )

        # Helper: render metrics ONLY when metrics_seq changes AND metrics text changed
        def _render_metrics(metrics_state):
            if metrics_state is None:
                return "&nbsp;"
            return metrics_state

        components["metrics_seq"].change(
            fn=_render_metrics,
            inputs=[components["metrics_state"]],
            outputs=[components["metrics"]],
            show_progress=False,
        )

        demo.queue()

    return demo


if __name__ == "__main__":
    demo = create_app()
    demo.launch()
