# ui/app.py
from __future__ import annotations

import gradio as gr

from memory.conversation import get_conversation_history
from ui.actions import (
    format_active_conversation,
    get_conversation_menu,
    load_user_profile_fields,
    update_history_display,
)
from ui.components import build_header, build_workspace, init_state
from ui.handlers import bind_live_actions, bind_profile_actions
from ui.poller import Poller
from ui.styles import CSS


def create_app():
    with gr.Blocks(css=CSS) as demo:
        components: dict[str, gr.Component] = {}
        init_state(components)

        with gr.Column(elem_id="app_shell"):
            build_header(components)
            build_workspace(components)

        bind_profile_actions(components)
        bind_live_actions(components)

        def _init_page():
            choices_update, label = components["_init_devices_fn"]()
            llm_options, llm_backend_update, llm_model_update, llm_status = components["_init_llm_fn"]()
            name, goal, mood, style, length, status = load_user_profile_fields()
            conv_choices, conv_selected, _ = get_conversation_menu()
            conv_heading = format_active_conversation(conv_selected)
            history = get_conversation_history()
            chat_html = update_history_display(history)

            return (
                choices_update,
                label,
                llm_options,
                llm_backend_update,
                llm_model_update,
                llm_status,
                name,
                goal,
                mood,
                style,
                length,
                status,
                gr.update(choices=conv_choices, value=conv_selected),
                conv_heading,
                history,
                chat_html,
            )

        demo.load(
            fn=_init_page,
            outputs=[
                components["device_dropdown"],
                components["device_current"],
                components["llm_options_state"],
                components["llm_backend"],
                components["llm_model"],
                components["llm_status"],
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

        poller = Poller()
        timer = gr.Timer(value=0.75, active=True)
        timer.tick(
            fn=poller.tick,
            inputs=[components["conversation_memory"]],
            outputs=[
                components["status_banner"],
                components["conversation_memory"],
                components["start_btn"],
                components["stop_btn"],
                components["tts_audio"],
                components["live_seq"],
                components["utter_ts_state"],
                components["reply_ts_state"],
                components["metrics_state"],
                components["metrics_seq"],
            ],
            show_progress=False,
            concurrency_limit=1,
        )

        def _render_history_and_timestamps(history, utter_ts_state, reply_ts_state):
            chat_html = update_history_display(history)

            if utter_ts_state is None:
                utter_label = "Utterance timing will appear here after the next turn."
            else:
                utter_label = f"Utterance: {utter_ts_state}"

            if reply_ts_state is None:
                reply_label = "Response timing will appear here after the next turn."
            else:
                reply_label = f"Response: {reply_ts_state}"

            return chat_html, utter_label, reply_label

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
