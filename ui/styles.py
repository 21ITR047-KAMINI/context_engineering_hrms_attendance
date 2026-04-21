import streamlit as st


def inject_custom_css():
    st.markdown(
        """
        <style>
        :root {
            --bg: #f4f6f8;
            --panel: #ffffff;
            --line: #e6eaf0;
            --text: #1f2937;
            --muted: #6b7280;
            --brand: #0f9d6c;
            --user: #08a36c;
        }

        header[data-testid="stHeader"], #MainMenu, footer {display:none !important;}
        .stApp, [data-testid="stAppViewContainer"], section.main {
            background: var(--bg) !important;
            color: var(--text);
        }

        [data-testid="stSidebar"] {
            background: #f7f8fa !important;
            border-right: 1px solid var(--line);
            margin-top: 56px;
        }

        .topbar {
            position: fixed; top: 0; left: 0; right: 0; z-index: 1000;
            height: 56px; display:flex; align-items:center; justify-content:space-between;
            background: #fff; border-bottom: 1px solid var(--line); padding: 0 14px;
        }
        .topbar-left,.topbar-right {display:flex; align-items:center; gap:10px;}
        .topbar-center {display:flex; justify-content:center; flex:1;}
        .brand-logo {height: 18px; width:auto;}
        .brand-title {font-weight:700; font-size:24px; color:#111827;}
        .status-pill {background:#dff5eb; color:#0b8f60; padding:6px 12px; border-radius:999px; font-size:14px; font-weight:600;}
        .icon-btn {background:transparent; border:none; font-size:16px; color:#4b5563; cursor:default;}
        .user-chip {font-size:14px; color:#374151;}

        .block-container {padding-top: 80px !important; padding-bottom: 120px !important; max-width: 1200px;}

        .stButton > button[kind="primary"] {
            background: var(--brand); border: none; border-radius: 10px; font-weight: 700;
            height: 46px;
        }

        .side-section {margin-top: 18px; color:#667085; font-weight:700; font-size:14px; display:flex; justify-content:space-between;}
        .history-label {margin-top:12px; font-weight:700; color:#8b95a7; font-size:14px;}
        .history-item {padding:10px; border-radius:10px; margin-top:8px; color:#334155; background:transparent;}
        .history-item.active {background:#e8f7f0; color:#047857;}
        .history-item small {color:#94a3b8;}
        .sidebar-user {position: sticky; bottom:10px; margin-top:20px; padding:10px; border-top:1px solid var(--line); display:flex; justify-content:space-between; align-items:center;}

        .chat-row {display:flex; margin: 12px 0;}
        .user-row {justify-content:flex-end;}
        .bot-row {justify-content:flex-start;}
        .chat-bubble {padding:16px; border-radius:14px; font-size:30px; line-height:1.4; max-width:75%;}
        .user-bubble {background: var(--user); color:#fff; border-bottom-right-radius:4px;}
        .bot-bubble {background:#fff; border:1px solid var(--line); border-bottom-left-radius:4px;}

        .assistant-card {background:#fff; border:1px solid var(--line); border-radius:16px; margin-top:18px;}
        .assistant-head {padding:18px 20px 10px; border-bottom:1px solid var(--line);}
        .assistant-title {font-size:30px; font-weight:700; color:#111827;}
        .assistant-sub {font-size:20px; color:#6b7280; margin-top:4px;}
        .assistant-body {padding:18px 20px; color:#374151; font-size:22px;}

        .kpi-grid {display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin:14px 0 20px;}
        .kpi-card {border-radius:14px; padding:16px; border:1px solid #e5e7eb; min-height:120px;}
        .kpi-card.positive {background:#e8f5ee;}
        .kpi-card.negative {background:#fdeff0;}
        .kpi-card.neutral {background:#f6f2e4;}
        .kpi-delta {font-size:20px; color:#6b7280; text-align:right;}
        .kpi-value {font-size:42px; font-weight:700; color:#111827; margin-top:8px;}
        .kpi-label {font-size:24px; color:#374151;}
        .kpi-sub {font-size:18px; color:#6b7280;}

        .thinking-text {font-style:italic; color:#6b7280; margin-left:6px;}

        div[data-testid="stChatInput"] {background:#fff !important; border:1px solid var(--line); border-radius:12px;}
        div[data-testid="stChatInput"] textarea {font-size:22px !important;}

        .system-footer {
            position: fixed; bottom:0; left:0; right:0; z-index: 999;
            background:#fff; border-top:1px solid var(--line); height:34px;
            display:flex; align-items:center; justify-content:center; gap:22px;
            color:#64748b; font-size:12px;
        }

        @media (max-width: 1000px) {
            .kpi-grid {grid-template-columns:1fr;}
            .assistant-title {font-size:22px;}
            .assistant-body {font-size:16px;}
            .chat-bubble {font-size:16px;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
