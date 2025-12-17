# ui/components.py
from __future__ import annotations
import gradio as gr


def init_state(components: dict) -> None:
    """Create global Gradio States used across tabs."""
    components["user_context"] = gr.State({})
    components["conversation_memory"] = gr.State([])  # active conversation history

    # (Legacy) Held the conversation dropdown value; kept for compatibility if needed
    components["conversation_dropdown_value"] = gr.State(None)

    # Hidden state that changes only when a NEW utterance is appended
    components["live_seq"] = gr.State(None)

    # Hidden states for utterance/response timestamps (raw values, not rendered text)
    components["utter_ts_state"] = gr.State(None)
    components["reply_ts_state"] = gr.State(None)

    # Hidden state for metrics text + its own sequence id
    components["metrics_state"] = gr.State(None)
    components["metrics_seq"] = gr.State(None)

    # State to control visibility of the per-conversation options menu (⋯)
    components["conv_menu_open_state"] = gr.State(False)


def build_header() -> None:
    with gr.Row():
        gr.Markdown("<h1 style='margin:0'>Jarvin - Your AI Assistant</h1>")


def build_profile_tab(components: dict) -> None:
    with gr.Tab("👤 User Profile"):
        gr.Markdown("### 🧠 Personalize Your Jarvin Experience")
        with gr.Row():
            with gr.Column():
                components["name"] = gr.Textbox(label="Your Name", placeholder="e.g., Kohei")
                components["goal"] = gr.Textbox(label="Current Goal / Task", placeholder="e.g., Working on a Flask app")
                components["mood"] = gr.Dropdown(
                    label="Your Current Mood",
                    choices=["Focused", "Stressed", "Curious", "Relaxed", "Tired", "Creative", "Problem-Solving"],
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
        components["save_btn"] = gr.Button("💾 Save Profile Settings")
        components["status"] = gr.Markdown("", elem_classes="status-text")


def build_live_tab(components: dict) -> None:
    with gr.Tab("🤖 Jarvin Live"):
        gr.Markdown("### 🎙️ Live listening (noise gate + VAD)")
        with gr.Row(elem_classes="live-grid"):
            # Controls column
            with gr.Column(scale=1, elem_id="control_col"):
                gr.Markdown("#### ⚙️ Controls", elem_id="controls_header")
                components["status_banner"] = gr.HTML("&nbsp;", elem_id="status_banner")
                with gr.Row(elem_classes="button_row"):
                    components["start_btn"] = gr.Button("▶ Start Listener")
                    components["stop_btn"] = gr.Button("⏸ Pause Listener")
                with gr.Row(elem_classes="button_row"):
                    components["shutdown_btn"] = gr.Button("🛑 Shutdown Jarvin")

                # ---- Conversations panel ----
                with gr.Accordion("🗂️ Conversations", open=True):
                    # New chat on top
                    components["new_conv_btn"] = gr.Button("➕ New chat")

                    # List + subtitle + inline ⋯ button in one wrapper
                    with gr.Group(elem_id="conv_list_wrapper"):
                        # List all conversations (radio), with active one styled via CSS
                        components["conv_list"] = gr.Radio(
                            label="Conversations",
                            choices=[],
                            value=None,
                            interactive=True,
                            show_label=False,
                            elem_classes=["conversation-list"],
                        )

                        # Subtitle is now hidden via CSS (kept for wiring)
                        components["conv_status"] = gr.Markdown(
                            "",
                            elem_classes=["status-text", "conv-status-hidden"],
                        )

                        # Single ⋯ button that always operates on the currently active chat
                        components["conv_menu_btn"] = gr.Button(
                            "⋯",
                            scale=0,
                            elem_id="conv_menu_button",
                        )


                    # Overlay menu for per-conversation actions
                    with gr.Group(visible=False, elem_id="conv_menu_overlay") as conv_menu_group:
                        with gr.Column(elem_classes="conv-menu-card"):
                            gr.Markdown(
                                "### Conversation settings",
                                elem_classes="conv-menu-title",
                            )
                            components["rename_conv_title"] = gr.Textbox(
                                label="Rename conversation",
                                placeholder="New title",
                            )
                            with gr.Row():
                                components["rename_conv_btn"] = gr.Button("Rename")
                                components["clear_conv_btn"] = gr.Button("Clear history")
                                components["delete_conv_btn"] = gr.Button(
                                    "Delete",
                                    elem_classes="clear-btn",
                                )
                            components["conv_error"] = gr.Markdown(
                                "",
                                elem_classes="status-text",
                            )
                            components["conv_menu_close_btn"] = gr.Button("Close")

                    components["conv_menu_group"] = conv_menu_group

                # (Conversation-level clear button is now inside the menu; no separate big clear button.)

            # Live / conversation column
            with gr.Column(scale=2, elem_id="live_col"):
                gr.Markdown("#### 💬 Conversation")

                # Single unified conversation log as a Chatbot (one scrollable UI element)
                components["chat_history"] = gr.Chatbot(
                    value=[],
                    label="",
                    show_label=False,
                    elem_id="history_box",
                    elem_classes=["conversation-history"],
                )

                components["tts_audio"] = gr.Audio(
                    label="🔊 Spoken Reply",
                    autoplay=True,
                    interactive=False,
                )

                # Rendered timestamps for utterance and response
                components["utter_ts_md"] = gr.Markdown(
                    "&nbsp;",
                    elem_classes="status-text",
                    visible=False,
                )
                components["reply_ts_md"] = gr.Markdown(
                    "&nbsp;",
                    elem_classes="status-text",
                    visible=False,
                )

                # Metrics bar (decoupled from polling via metrics_state/metrics_seq)
                components["metrics"] = gr.HTML("&nbsp;", elem_id="metrics_bar")

        # 🎤 Microphone controls
        with gr.Accordion("🎤 Microphone", open=False):
            components["device_current"] = gr.Markdown("", elem_classes="status-text")
            with gr.Row():
                components["device_dropdown"] = gr.Dropdown(
                    label="Input device",
                    choices=[],   # populated on load
                    value=None,
                    interactive=True,
                )
                components["device_refresh_btn"] = gr.Button("🔄 Refresh", scale=0)
