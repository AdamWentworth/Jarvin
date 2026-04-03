CSS = """
:root {
    --bg: #0b1220;
    --bg-soft: #101a2b;
    --panel: rgba(14, 22, 38, 0.92);
    --panel-soft: rgba(18, 28, 46, 0.88);
    --panel-muted: rgba(13, 20, 34, 0.78);
    --border: rgba(89, 110, 145, 0.28);
    --border-strong: rgba(96, 124, 173, 0.38);
    --text: #e8edf5;
    --text-muted: #a9b8cf;
    --accent: #4f8cff;
    --accent-strong: #2f6fed;
    --danger: #cf4f4f;
    --success: #0f766e;
    --shadow: 0 22px 48px rgba(0, 0, 0, 0.22);
}

html,
body {
    background:
        radial-gradient(circle at top left, rgba(58, 91, 152, 0.18), transparent 34%),
        linear-gradient(180deg, #0b1220 0%, #0d1524 100%);
    color: var(--text);
    font-family: "Aptos", "Segoe UI", "Trebuchet MS", sans-serif;
}

body {
    margin: 0;
}

.gradio-container {
    max-width: 1480px !important;
    padding: 18px 18px 28px !important;
}

#app_shell {
    gap: 18px;
}

#topbar {
    align-items: stretch;
    gap: 16px;
    margin-bottom: 4px;
}

#brand_block,
#utility_shell,
#sidebar_shell,
#workspace_shell,
#chat_shell,
#composer_shell {
    border: 1px solid var(--border);
    border-radius: 20px;
    background: var(--panel);
    box-shadow: var(--shadow);
}

#brand_block {
    padding: 18px 20px 16px;
    min-height: 104px;
    justify-content: center;
}

#app_title .prose {
    margin: 0;
    font-size: 1.85rem;
    letter-spacing: -0.02em;
}

.shell-subtitle,
.shell-subtitle .prose {
    color: var(--text-muted);
    margin: 6px 0 0 0 !important;
}

#utility_block {
    min-width: 0;
}

#utility_shell {
    height: 100%;
    padding: 14px 16px;
    background: var(--panel-soft);
}

.utility_row {
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}

#status_banner,
#status_banner .prose {
    flex: 1 1 260px;
    min-height: 38px;
    margin: 0 !important;
    display: flex;
    align-items: center;
}

.status-text {
    color: var(--text-muted);
    font-weight: 600;
    margin: 0;
}

.status-badge {
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 999px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
}

.status-listening {
    background: rgba(15, 118, 110, 0.18);
    color: #7ce9de;
}

.status-recording {
    background: rgba(180, 57, 57, 0.22);
    color: #ffc0c0;
}

.status-stopped {
    background: rgba(71, 85, 105, 0.32);
    color: #d6deeb;
}

.gr-button,
button.primary,
button.secondary {
    border: none !important;
    border-radius: 12px !important;
    min-height: 40px !important;
    padding: 0 16px !important;
    font-weight: 700 !important;
    background: linear-gradient(180deg, var(--accent) 0%, var(--accent-strong) 100%) !important;
    color: #f8fbff !important;
    box-shadow: none !important;
}

.gr-button:hover {
    filter: brightness(1.05);
}

.clear-btn button,
#shutdown_btn button {
    background: linear-gradient(180deg, #bb5050 0%, #a33c3c 100%) !important;
}

.button_row {
    gap: 10px;
}

#workspace_grid {
    display: grid !important;
    grid-template-columns: 300px minmax(0, 1fr);
    gap: 18px;
    align-items: start;
}

#sidebar_shell {
    padding: 16px;
    background: var(--panel-soft);
}

.panel-title .prose {
    margin: 0 !important;
}

.panel-caption,
.panel-caption .prose {
    color: var(--text-muted);
    margin: 4px 0 0 0 !important;
}

#conversation_list {
    margin-top: 10px;
}

.conversation-list {
    max-height: 62vh;
    overflow-y: auto;
    padding-right: 4px;
}

.conversation-list .gr-radio {
    padding: 0;
    background: transparent;
}

.conversation-list .gr-radio label {
    display: flex;
    align-items: center;
    padding: 10px 12px;
    border-radius: 12px;
    margin-bottom: 6px;
    cursor: pointer;
    background: rgba(11, 18, 31, 0.88);
    color: var(--text);
    border: 1px solid transparent;
    transition: background 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
}

.conversation-list .gr-radio label:hover {
    background: rgba(18, 29, 49, 0.96);
    border-color: var(--border);
    transform: translateY(-1px);
}

.conversation-list .gr-radio label:has(input[type="radio"]:checked) {
    background: rgba(26, 45, 76, 0.98);
    border-color: rgba(92, 130, 201, 0.62);
    color: #f8fbff;
}

#workspace_shell {
    padding: 16px;
    min-width: 0;
    background: linear-gradient(180deg, rgba(14, 22, 38, 0.96) 0%, rgba(10, 17, 30, 0.98) 100%);
}

#conversation_heading,
#conversation_heading .prose {
    margin: 0 0 12px 0 !important;
}

#chat_shell {
    overflow: hidden;
    background: rgba(11, 18, 31, 0.92);
}

.conversation-history {
    height: 62vh;
    min-height: 420px;
    max-height: 68vh;
    overflow-y: auto !important;
    border: none !important;
    border-radius: 0;
    padding: 18px;
    background: transparent !important;
}

.conversation-history::-webkit-scrollbar,
.conversation-list::-webkit-scrollbar {
    width: 8px;
}

.conversation-history::-webkit-scrollbar-track,
.conversation-list::-webkit-scrollbar-track {
    background: rgba(26, 40, 64, 0.88);
    border-radius: 999px;
}

.conversation-history::-webkit-scrollbar-thumb,
.conversation-list::-webkit-scrollbar-thumb {
    background: rgba(93, 114, 148, 0.9);
    border-radius: 999px;
}

#composer_shell {
    border: none;
    border-top: 1px solid var(--border-strong);
    border-radius: 0 0 20px 20px;
    padding: 14px;
    background: rgba(9, 15, 26, 0.96);
    box-shadow: none;
}

.chat-status,
.chat-status .prose {
    margin: 0 0 10px 0 !important;
}

#chat_input_box textarea {
    background: rgba(10, 17, 29, 0.98) !important;
    color: #f8fbff !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 16px !important;
    padding: 14px !important;
    min-height: 110px !important;
}

.composer_actions {
    align-items: end;
    gap: 12px;
    margin-top: 10px;
}

#chat_mode_select {
    min-width: 220px;
}

#chat_send_btn button {
    min-width: 148px;
}

.chat-mode-hint,
.chat-mode-hint .prose {
    margin: 10px 0 0 0 !important;
}

#model_settings,
#voice_settings,
#profile_settings,
#diagnostics_settings {
    margin-top: 12px;
    border: 1px solid var(--border) !important;
    border-radius: 16px !important;
    background: var(--panel-muted) !important;
}

#model_settings .label-wrap,
#voice_settings .label-wrap,
#profile_settings .label-wrap,
#diagnostics_settings .label-wrap {
    color: var(--text);
}

.profile_grid {
    gap: 14px;
}

#metrics_bar,
#metrics_bar .prose {
    margin: 8px 0 0 0 !important;
    min-height: 26px;
    color: var(--text-muted);
    font-family: "Cascadia Code", "Consolas", monospace;
    white-space: normal;
}

#conv_menu_overlay {
    position: fixed !important;
    inset: 0 !important;
    z-index: 1000;
    background: rgba(3, 8, 17, 0.48) !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
}

#conv_menu_overlay > .styler {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    display: flex;
    justify-content: center;
    align-items: flex-start;
}

#conv_menu_overlay .conv-menu-card {
    background: rgba(16, 24, 39, 0.98) !important;
    border: 1px solid var(--border-strong);
    border-radius: 18px;
    padding: 18px 20px;
    width: min(460px, calc(100vw - 32px));
    margin: 10vh auto 0 auto;
    box-shadow: 0 24px 64px rgba(0, 0, 0, 0.35);
}

#conv_menu_overlay .conv-menu-card .block {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

.gr-markdown,
.gr-prose,
.prose {
    margin-top: 0.2rem;
    margin-bottom: 0.2rem;
}

@media (max-width: 1100px) {
    #workspace_grid {
        grid-template-columns: 260px minmax(0, 1fr);
    }
}

@media (max-width: 900px) {
    .gradio-container {
        padding: 12px 12px 20px !important;
    }

    #topbar,
    #workspace_grid {
        display: flex !important;
        flex-direction: column;
    }

    #main_col {
        order: 1;
    }

    #sidebar_col {
        order: 2;
    }

    #brand_block,
    #utility_shell,
    #sidebar_shell,
    #workspace_shell {
        border-radius: 18px;
    }

    .conversation-history {
        min-height: 360px;
        height: 52vh;
    }

    .composer_actions {
        flex-direction: column;
        align-items: stretch;
    }

    #chat_send_btn button {
        width: 100%;
    }
}
"""
