import streamlit as st

def inject_custom_css():
    st.markdown("""
    <style>
    :root {
        --bg-start: #f3f7ff;
        --bg-mid: #eef7f0;
        --bg-end: #f8fafc;
        --brand: #1d4ed8;
        --brand-strong: #1e40af;
        --text-primary: #0f172a;
        --text-secondary: #475569;
        --panel: #ffffff;
        --border: #dbe3ee;
    }

    /* ==========================================
       REMOVE STREAMLIT DEFAULT UI
    ========================================== */

    header[data-testid="stHeader"] {display:none;}
    footer {visibility:hidden;}

    /* ==========================================
       FULL BACKGROUND
    ========================================== */

    html, body, [data-testid="stAppViewContainer"], .stApp {
        background: linear-gradient(
            135deg,
            var(--bg-start) 0%,
            var(--bg-mid) 45%,
            var(--bg-end) 100%
        ) !important;
        color: var(--text-primary);
        font-size: 18px;
    }

    /* REMOVE ALL BLOCK BACKGROUNDS */
    [data-testid="stAppViewContainer"] > .main,
    section.main,
    section.main > div,
    .block-container {
        background: transparent !important;
    }

    /* FIX BOTTOM AREA */
    [data-testid="stBottomBlockContainer"] {
        background: linear-gradient(
            135deg,
            #e6f4ea 0%,
            #f5f7f6 40%,
            #eef2f1 100%
        ) !important;
    }

    div[data-testid="stBottom"] {
        background: transparent !important;
    }

    /* FORCE REMOVE DARK BACKGROUND (FINAL FIX) */
    [data-testid="stBottomBlockContainer"],
    [data-testid="stBottomBlockContainer"] > div,
    div[data-testid="stBottom"] > div {
        background: transparent !important;
    }

    /* ==========================================
       HEADER
    ========================================== */

    .custom-header {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 60px;

        display: flex;
        justify-content: space-between;
        align-items: center;

        padding: 0 40px;

        background: rgba(255,255,255,0.92);
        backdrop-filter: blur(14px);

        border-bottom: 1px solid var(--border);
        z-index: 9999;
    }

    .header-left {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }

    .product-title {
        font-size: 1.4rem;
        font-weight: 700;
        letter-spacing: 0.1px;
    }

    .product-subtitle {
        font-size: 1rem;
        color: var(--text-secondary);
    }
                
    .header-right img {
        height: 120px;
        width: auto;
    }

    /* ==========================================
       MAIN CONTAINER
    ========================================== */

    .block-container {
        padding-top: 124px !important;
        padding-bottom: 120px !important;
        max-width: 100% !important;
        width: 100% !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }

    /* ==========================================
       CHAT BUBBLES
    ========================================== */

    .chat-row {
        display: flex;
        margin: 10px 0;
        width: 100%;
    }

    .empty-state-wrap {
        display: flex;
        justify-content: center;
        margin-top: 28px;
        margin-bottom: 24px;
    }

    .empty-state-card {
        width: min(980px, 100%);
        background: rgba(255,255,255,0.9);
        border: 1px solid var(--border);
        border-radius: 16px;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
        padding: 22px 24px;
    }

    .empty-state-card h3 {
        margin: 0 0 6px 0;
        font-size: 1.1rem;
    }

    .empty-state-card p {
        margin: 0;
        color: var(--text-secondary);
        font-size: 0.95rem;
    }

    .empty-state-prompts {
        margin-top: 14px;
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
    }

    .empty-state-prompts span {
        display: inline-block;
        background: #eff6ff;
        border: 1px solid #c8d9ff;
        color: #1e3a8a;
        padding: 6px 10px;
        border-radius: 999px;
        font-size: 0.82rem;
        font-weight: 500;
    }

    .user-row {
        justify-content: flex-end;
    }

    .bot-row {
        justify-content: flex-start;
    }

    .chat-bubble {
    max-width: 80%;
    padding: 12px 16px;
    border-radius: 14px;
    font-size: 24px;
    line-height: 0.5;
    word-wrap: break-word;
    overflow-wrap: break-word;
    white-space: pre-wrap;
    box-shadow: 0 4px 14px rgba(15, 23, 42, 0.06);
    }

    .full-response-bubble {
    max-width: 96% !important;
    width: 96%;
    }
                
    .user-bubble {
        background: linear-gradient(135deg, var(--brand), #2563eb);
        color: white;
        border-bottom-right-radius: 4px;
    }

    .bot-bubble {
    background: var(--panel);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-bottom-left-radius: 4px;
    width: 100%;
    max-width: 100%;
}
     .thinking-text {
    font-size: 14px;
    color: var(--text-secondary);
    margin-left: 6px;
    font-style: italic;
    opacity: 0.8;
}
                
    /* ==========================================
       FIX CHAT INPUT (FINAL)
    ========================================== */
        /* ==========================================
   CHAT INPUT - FIXED
========================================== */

    div[data-testid="stChatInput"] {
        position: fixed !important;
        bottom: 40px !important;
        left: 0 !important;
        right: 0 !important;
        width: 100vw !important;
        max-width: 100vw !important;

        padding: 10px 24px !important;
        background: rgba(255,255,255,0.96) !important;
        border-top: 1px solid var(--border) !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        z-index: 999;
    }

    /* center the input content */
    div[data-testid="stChatInput"] > div {
        width: 100% !important;
        max-width: 1200px !important;
        margin: 0 auto !important;
        background: transparent !important;
    }

    /* remove Streamlit/BaseWeb dark wrappers */
    div[data-testid="stChatInput"] div {
        background: transparent !important;
    }

    /* actual input box */
    div[data-testid="stChatInput"] textarea {
        width: 100% !important;
        min-height: 44px !important;
        max-height: 120px !important;

        background: #ffffff !important;
        color: var(--text-primary) !important;

        border: 1px solid var(--border) !important;
        border-radius: 12px !important;

        padding: 10px 48px 10px 14px !important;
        font-size: 18px !important;
        line-height: 0.9 !important;

        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08) !important;
        outline: none !important;
    }

    /* placeholder */
    div[data-testid="stChatInput"] textarea::placeholder {
        color: var(--text-secondary) !important;
        font-size: 14px !important;
    }

    /* send button */
    div[data-testid="stChatInput"] button {
        background-color: var(--brand) !important;
        color: white !important;
        border-radius: 8px !important;
        margin: 0 !important;
        position: absolute !important;
        right: 36px !important;
        bottom: 18px !important;
    }

    /* remove pseudo elements */
    div[data-testid="stChatInput"]::before,
    div[data-testid="stChatInput"]::after {
        display: none !important;
    }
    /* ==========================================
       FOOTER
    ========================================== */

    .custom-footer {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        height: 40px;

        text-align: center;
        font-size: 12px;
        color: #666;

        background: transparent;
        border-top: 1px solid var(--border);

        line-height: 40px;
        z-index: 1000;
    }

    </style>
    """, unsafe_allow_html=True)
