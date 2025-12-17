# ui/styles.py

CSS = """
/* ---- Base theme ---- */
body {
    background-color: #1f1f2e;
    color: #f5f5f5;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

.gradio-container {
    border-radius: 12px;
    padding: 20px;
}

.tab-content {
    background-color: #2c2c3e;
    border-radius: 8px;
    padding: 20px;
    margin-top: 10px;
}

/* ---- Buttons ---- */
.gr-button {
    background-color: #4f46e5;
    color: white;
    border-radius: 8px;
    border: none;
    padding: 10px 20px;
    font-weight: bold;
    margin: 5px;
    min-height: 40px; /* stable */
}
.gr-button:hover { background-color: #6366f1; }
.clear-btn { background-color: #dc2626 !important; }
.clear-btn:hover { background-color: #ef4444 !important; }
.button_row { gap: 8px; }

/* ---- Tabs ---- */
.gradio-tabs button {
    background-color: #3b3b4e;
    color: #f5f5f5;
    border-radius: 8px 8px 0 0;
    padding: 10px 20px;
    margin-right: 2px;
    font-weight: bold;
}
.gradio-tabs button:focus { outline: none; background-color: #57577f; }

/* ---- Status & info ---- */
.status-text { color: #10b981; font-weight: bold; margin: 10px 0; }

/* Color tokens for state badges */
.status-badge {
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 6px;
    display: inline-block;
}
.status-listening { background: #064e3b; color: #a7f3d0; }   /* green */
.status-recording { background: #7f1d1d; color: #fecaca; }   /* red */
.status-stopped   { background: #374151; color: #e5e7eb; }   /* gray */

/* Spinner for “LLM thinking” */
.spinner {
    display: inline-block;
    width: 12px; height: 12px;
    border: 2px solid rgba(255,255,255,0.25);
    border-top-color: rgba(255,255,255,0.9);
    border-radius: 50%;
    animation: spin 0.9s linear infinite;
    margin-right: 6px;
    vertical-align: -1px;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ---- Live tab stable grid ---- */
.live-grid {
    display: grid !important;
    grid-template-columns: 360px minmax(0, 1fr);
    gap: 16px;
    align-items: start;
}

/* Controls column header spacing */
#controls_header .prose { margin: 0 !important; }

/* Reserve fixed height for banner & metrics to prevent layout shift */
#status_banner,
#status_banner .prose {
    min-height: 28px;
    line-height: 28px;
    margin: 0 !important;
    display: block;
}
#metrics_bar,
#metrics_bar .prose {
    min-height: 24px;
    line-height: 24px;
    margin: 8px 0 0 0 !important;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    letter-spacing: 0.2px;
}

/* Conversation history – single scrollable Chatbot region (taller) */
.conversation-history {
    max-height: 640px;
    height: 640px;
    overflow-y: auto !important;
    border: 1px solid #4b5563 !important;
    border-radius: 8px;
    padding: 10px;
    background-color: #374151 !important;
}
.conversation-history::-webkit-scrollbar { width: 8px; }
.conversation-history::-webkit-scrollbar-track { background: #4b5563; border-radius: 4px; }
.conversation-history::-webkit-scrollbar-thumb { background: #6b7280; border-radius: 4px; }
.conversation-history::-webkit-scrollbar-thumb:hover { background: #9ca3af; }

/* Conversation list (radio) */
.conversation-list {
    max-height: 260px;
    overflow-y: auto;
}

/* (Legacy bubble styles kept; no longer used now that Chatbot handles layout)
.chatline {
    display: flex;
    margin: 6px 0;
}
.chatline .bubble {
    max-width: 80%;
    padding: 8px 12px;
    border-radius: 14px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.25);
}
.chatline.user   { justify-content: flex-end; }
.chatline.user .bubble {
    background: #2563eb;
    color: white;
    border-bottom-right-radius: 4px;
}
.chatline.assistant { justify-content: flex-start; }
.chatline.assistant .bubble {
    background: #111827;
    color: #f3f4f6;
    border-bottom-left-radius: 4px;
}
*/

/* Minor: trim default markdown margins globally to avoid bumps */
.gr-markdown, .gr-prose, .prose { margin-top: 0.25rem; margin-bottom: 0.25rem; }

/* Conversation list: active row background color + hover ⋯ indicator */
.conversation-list .gr-radio {
    padding: 0;
    background: transparent;
}

.conversation-list .gr-radio label {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 10px;
    border-radius: 6px;
    margin-bottom: 4px;
    cursor: pointer;
    background: #111827;          /* default background for all rows */
    color: #e5e7eb;
    transition: background 0.15s ease, color 0.15s ease;
}

/* Hover state for any conversation row */
.conversation-list .gr-radio label:hover {
    background: #1f2937;
}

/* Ellipsis on hover, aligned to the right */
.conversation-list .gr-radio label::after {
    content: "⋯";
    opacity: 0;
    font-weight: 700;
    margin-left: 8px;
    transition: opacity 0.15s ease;
}

.conversation-list .gr-radio label:hover::after {
    opacity: 1;
}

/* Active conversation row (different background color) */
.conversation-list .gr-radio label:has(input[type="radio"]:checked) {
    background: #4f46e5;          /* active background */
    color: #f9fafb;
}

/* Hide the old "active conversation" subtitle completely */
.conv-status-hidden {
    display: none !important;
}

/* Conversation settings overlay */
#conv_menu_overlay {
    position: fixed !important;
    inset: 0 !important;
    z-index: 1000;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
}

/* Gradio's wrapper around the card (the .styler div) – kill its background */
#conv_menu_overlay > .styler {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;

    display: flex;
    justify-content: center;
    align-items: flex-start;
}

/* The actual card: only this should have a background */
#conv_menu_overlay .conv-menu-card {
    background-color: #111827 !important;  /* card background ONLY */
    border-radius: 12px;
    padding: 16px 20px;

    flex-grow: 0 !important;               /* don't stretch full width */
    width: 100%;
    max-width: 420px;
    margin: 10vh auto 0 auto;
}

/* Optional: inner blocks inside the card inherit the card bg, not their own */
#conv_menu_overlay .conv-menu-card .block {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

/* Minor spacing for overlay title */
#conv_menu_overlay .conv-menu-title .prose {
    margin-bottom: 0.5rem;
}

/* Ellipsis button that triggers the overlay (acts on active chat) */
/* Wrapper around conversation list + status + ⋯ button */
#conv_list_wrapper {
    position: relative;
}

/* Ellipsis button visually inline with the conversations list */
#conv_menu_button {
    position: absolute;
    top: 6px;
    right: 6px;
    width: 28px;
    min-width: 28px;
    padding: 0;
    line-height: 1;
    z-index: 5;
}
"""