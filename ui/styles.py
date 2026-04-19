import streamlit as st

def inject_custom_css():
    st.markdown("""
    <style>

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
            #addfad 0%,
            #c6ebc9 40%,
            #eaf7ed 100%
        ) !important;
        color: #1a1a1a;
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
        height: 70px;

        display: flex;
        justify-content: space-between;
        align-items: center;

        padding: 0 30px;

        background: rgba(255,255,255,0.6);
        backdrop-filter: blur(10px);

        border-bottom: 1px solid #ddd;
        z-index: 9999;
    }

    .header-left {
        font-size: 20px;
        font-weight: 600;
    }

    .header-right img {
        height: 40px;
    }

    /* ==========================================
       MAIN CONTAINER
    ========================================== */

    .main-container {
    margin-top: 90px;
    margin-bottom: 120px;
    max-width: 1200px;
    width: 100%;
    margin-left: auto;
    margin-right: auto;
    padding: 0 24px;
    box-sizing: border-box;
    }
                
    /* ==========================================
       CHAT BUBBLES
    ========================================== */

    .chat-row {
        display: flex;
        margin: 10px 0;
        width: 100%;
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
    font-size: 16px;
    line-height: 1.5;
    word-wrap: break-word;
    overflow-wrap: break-word;
    }

    .full-response-bubble {
    max-width: 96% !important;
    width: 96%;
    }
                
    .user-bubble {
        background: #4f46e5;
        color: white;
        border-bottom-right-radius: 4px;
    }

    .bot-bubble {
    background: white;
    color: #1a1a1a;
    border: 1px solid #ddd;
    border-bottom-left-radius: 4px;
    width: 100%;
    max-width: 100%;
}
     .thinking-text {
    font-size: 14px;
    color: #4b6b57;
    margin-left: 6px;
    font-style: italic;
    opacity: 0.8;
}
                
    /* ==========================================
       FIX CHAT INPUT (FINAL)
    ========================================== */

    /* OUTER CONTAINER */
    div[data-testid="stChatInput"] {
        max-width: 700px;
        margin: auto;

        background: #e6f4ea !important;
        border-radius: 12px !important;
        padding: 12px !important;
        border: none !important;

        box-shadow: none;
    }

    /* REMOVE INNER DARK LAYER */
    div[data-testid="stChatInput"] > div {
        background: transparent !important;
    }

    /* REMOVE ANY DARK WRAPPER AROUND INPUT */
    div[data-testid="stChatInput"]::before,
    div[data-testid="stChatInput"]::after {
        display: none !important;
    }

    /* TEXT AREA */
    div[data-testid="stChatInput"] textarea {
        background: #dff5e3 !important;
        color: #1a1a1a !important;
        border-radius: 8px !important;
        border: none !important;
        outline: none !important;
        font-size: 16px !important;
    }

    /* PLACEHOLDER */
    div[data-testid="stChatInput"] textarea::placeholder {
        color: #4b6b57 !important;
        font-size: 16px !important;
    }

    /* SEND BUTTON */
    div[data-testid="stChatInput"] button {
        background-color: #4CAF50 !important;
        color: white !important;
        border-radius: 6px !important;
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
        border-top: 1px solid #ddd;

        line-height: 40px;
        z-index: 1000;
    }

    </style>
    """, unsafe_allow_html=True)