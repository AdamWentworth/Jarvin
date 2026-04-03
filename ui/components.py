from __future__ import annotations

import gradio as gr

from backend.ai_engine import DEFAULT_CHAT_MODE, mode_choice_pairs, mode_hint


def init_state(components: dict) -> None:
    """Create global Gradio States used across the workspace."""
    components["user_context"] = gr.State({})
    components["conversation_memory"] = gr.State([])
    components["llm_options_state"] = gr.State({})
    components["conversation_dropdown_value"] = gr.State(None)
    components["live_seq"] = gr.State(None)
    components["utter_ts_state"] = gr.State(None)
    components["reply_ts_state"] = gr.State(None)
    components["metrics_state"] = gr.State(None)
    components["metrics_seq"] = gr.State(None)
    components["conv_menu_open_state"] = gr.State(False)


def build_header(components: dict) -> None:
    with gr.Row(elem_id="topbar"):
        with gr.Column(scale=2, elem_id="brand_block"):
            gr.Markdown("## Jarvin", elem_id="app_title")
            gr.Markdown(
                "Private local assistant for chat, voice, and agent work.",
                elem_classes=["shell-subtitle"],
            )

        with gr.Column(scale=3, elem_id="utility_block"):
            with gr.Group(elem_id="utility_shell"):
                with gr.Row(elem_classes="utility_row"):
                    components["status_banner"] = gr.HTML("&nbsp;", elem_id="status_banner")
                    components["start_btn"] = gr.Button(
                        "Start",
                        elem_id="listener_start_btn",
                    )
                    components["stop_btn"] = gr.Button(
                        "Pause",
                        elem_id="listener_stop_btn",
                    )
                    components["shutdown_btn"] = gr.Button(
                        "Shutdown",
                        elem_id="shutdown_btn",
                        elem_classes=["clear-btn"],
                    )


def build_workspace(components: dict) -> None:
    with gr.Row(elem_classes="workspace-grid", elem_id="workspace_grid"):
        with gr.Column(scale=1, elem_id="sidebar_col"):
            with gr.Group(elem_id="sidebar_shell"):
                gr.Markdown("### Conversations", elem_classes=["panel-title"])
                gr.Markdown(
                    "Recent chats stay here so the main workspace can stay focused.",
                    elem_classes=["panel-caption"],
                )

                with gr.Row(elem_classes="button_row"):
                    components["new_conv_btn"] = gr.Button(
                        "New chat",
                        elem_id="new_conv_btn",
                    )
                    components["conv_menu_btn"] = gr.Button(
                        "Manage chat",
                        elem_id="conv_menu_button",
                    )

                components["conv_list"] = gr.Radio(
                    label="Conversations",
                    choices=[],
                    value=None,
                    interactive=True,
                    show_label=False,
                    elem_classes=["conversation-list"],
                    elem_id="conversation_list",
                )

                with gr.Group(visible=False, elem_id="conv_menu_overlay") as conv_menu_group:
                    with gr.Column(elem_classes="conv-menu-card"):
                        gr.Markdown("### Conversation settings", elem_classes="conv-menu-title")
                        components["rename_conv_title"] = gr.Textbox(
                            label="Rename conversation",
                            placeholder="New title",
                        )
                        with gr.Row():
                            components["rename_conv_btn"] = gr.Button("Rename")
                            components["clear_conv_btn"] = gr.Button("Clear history")
                            components["delete_conv_btn"] = gr.Button(
                                "Delete",
                                elem_classes=["clear-btn"],
                            )
                        components["conv_error"] = gr.Markdown(
                            "",
                            elem_classes="status-text",
                        )
                        components["conv_menu_close_btn"] = gr.Button("Close")

                components["conv_menu_group"] = conv_menu_group

        with gr.Column(scale=3, elem_id="main_col"):
            with gr.Group(elem_id="workspace_shell"):
                components["conv_status"] = gr.Markdown(
                    "### New conversation",
                    elem_id="conversation_heading",
                )

                with gr.Group(elem_id="chat_shell"):
                    components["chat_history"] = gr.Chatbot(
                        value=[],
                        label="",
                        show_label=False,
                        elem_id="history_box",
                        elem_classes=["conversation-history"],
                    )

                    with gr.Group(elem_id="composer_shell"):
                        components["chat_status"] = gr.Markdown(
                            "&nbsp;",
                            elem_classes=["status-text", "chat-status"],
                        )
                        components["chat_input"] = gr.Textbox(
                            label="",
                            placeholder="Message Jarvin...",
                            lines=4,
                            show_label=False,
                            elem_id="chat_input_box",
                        )
                        with gr.Row(elem_classes="composer_actions"):
                            components["chat_mode"] = gr.Dropdown(
                                label="Mode",
                                choices=mode_choice_pairs(),
                                value=DEFAULT_CHAT_MODE,
                                interactive=True,
                                elem_id="chat_mode_select",
                            )
                            components["chat_send_btn"] = gr.Button(
                                "Send message",
                                elem_id="chat_send_btn",
                            )
                        components["chat_mode_hint"] = gr.Markdown(
                            mode_hint(DEFAULT_CHAT_MODE),
                            elem_classes=["status-text", "chat-mode-hint"],
                        )

                        with gr.Accordion("Model & Backend", open=False, elem_id="model_settings"):
                            gr.Markdown(
                                "These settings apply to Jarvin globally for now.",
                                elem_classes=["status-text", "panel-caption"],
                            )
                            components["llm_backend"] = gr.Dropdown(
                                label="LLM Backend",
                                choices=[],
                                value=None,
                                interactive=True,
                            )
                            components["llm_model"] = gr.Dropdown(
                                label="Model",
                                choices=[],
                                value=None,
                                interactive=True,
                            )
                            with gr.Row(elem_classes="button_row"):
                                components["llm_refresh_btn"] = gr.Button("Refresh Models")
                                components["llm_apply_btn"] = gr.Button("Apply LLM Settings")
                            components["llm_status"] = gr.Markdown("&nbsp;", elem_classes="status-text")

                        with gr.Accordion("Voice & Devices", open=False, elem_id="voice_settings"):
                            gr.Markdown(
                                "Device controls stay available here while typed chat remains the main focus.",
                                elem_classes=["status-text", "panel-caption"],
                            )
                            components["device_current"] = gr.Markdown(
                                "",
                                elem_classes="status-text",
                            )
                            with gr.Row(elem_classes="button_row"):
                                components["device_dropdown"] = gr.Dropdown(
                                    label="Input device",
                                    choices=[],
                                    value=None,
                                    interactive=True,
                                )
                                components["device_refresh_btn"] = gr.Button("Refresh", scale=0)

                        with gr.Accordion(
                            "Profile & Personalization",
                            open=False,
                            elem_id="profile_settings",
                        ):
                            gr.Markdown(
                                "Saved preferences help Jarvin stay consistent across conversations.",
                                elem_classes=["status-text", "panel-caption"],
                            )
                            with gr.Row(elem_classes="profile_grid"):
                                with gr.Column():
                                    components["name"] = gr.Textbox(
                                        label="Your Name",
                                        placeholder="e.g., Kohei",
                                    )
                                    components["goal"] = gr.Textbox(
                                        label="Current Goal / Task",
                                        placeholder="e.g., Working on a Flask app",
                                    )
                                    components["mood"] = gr.Dropdown(
                                        label="Your Current Mood",
                                        choices=[
                                            "Focused",
                                            "Stressed",
                                            "Curious",
                                            "Relaxed",
                                            "Tired",
                                            "Creative",
                                            "Problem-Solving",
                                        ],
                                        value="Focused",
                                    )
                                with gr.Column():
                                    components["communication_style"] = gr.Dropdown(
                                        label="Preferred Communication Style",
                                        choices=["Friendly", "Professional", "Casual", "Encouraging", "Direct"],
                                        value="Friendly",
                                    )
                                    components["response_length"] = gr.Dropdown(
                                        label="Preferred Response Length",
                                        choices=["Concise", "Balanced", "Detailed"],
                                        value="Balanced",
                                    )
                            components["save_btn"] = gr.Button("Save Profile Settings")
                            components["status"] = gr.Markdown("&nbsp;", elem_classes="status-text")

                        with gr.Accordion("Diagnostics", open=False, elem_id="diagnostics_settings"):
                            gr.Markdown(
                                "Operational details live here so they stay out of the main chat flow.",
                                elem_classes=["status-text", "panel-caption"],
                            )
                            components["tts_audio"] = gr.Audio(
                                label="Spoken Reply",
                                autoplay=True,
                                interactive=False,
                            )
                            components["utter_ts_md"] = gr.Markdown(
                                "Utterance timing will appear here after the next turn.",
                                elem_classes="status-text",
                            )
                            components["reply_ts_md"] = gr.Markdown(
                                "Response timing will appear here after the next turn.",
                                elem_classes="status-text",
                            )
                            components["metrics"] = gr.HTML("&nbsp;", elem_id="metrics_bar")
