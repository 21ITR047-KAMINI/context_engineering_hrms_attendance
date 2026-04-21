import base64
import streamlit as st


def get_logo_base64():
    try:
        with open("assets/Rnd_Optimizar_logo.png", "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception as e:
        print("Logo load error:", e)
        return ""


def render_header():
    logo_base64 = get_logo_base64()

    html = f"""
    <div class="topbar">
        <div class="topbar-left">
            <button class="icon-btn">☰</button>
            <img src="data:image/png;base64,{logo_base64}" class="brand-logo" alt="logo" />
            <span class="brand-title">HR Attendance AI</span>
        </div>

        <div class="topbar-center">
            <span class="status-pill">● AI Assistant Active</span>
        </div>

        <div class="topbar-right">
            <button class="icon-btn">◐</button>
            <button class="icon-btn">🔔</button>
            <span class="user-chip">Sarah Chen ▾</span>
        </div>
    </div>
    """

    st.markdown(html, unsafe_allow_html=True)


def render_sidebar():
    with st.sidebar:
        st.markdown("<div class='sidebar-wrap'>", unsafe_allow_html=True)

        st.button("＋  New Chat", use_container_width=True, type="primary")

        st.markdown("<div class='side-section'>QUICK FILTERS <span>⌄</span></div>", unsafe_allow_html=True)
        st.markdown("<div class='side-section'>SAVED PROMPTS <span>⌄</span></div>", unsafe_allow_html=True)
        st.markdown("<div class='side-section'>HISTORY</div>", unsafe_allow_html=True)

        st.markdown("<div class='history-label'>Today</div>", unsafe_allow_html=True)
        st.markdown("<div class='history-item active'>Attendance summary last 30 days<br><small>10:14 AM</small></div>", unsafe_allow_html=True)
        st.markdown("<div class='history-item'>Late arrivals in Engineering Q1<br><small>9:02 AM</small></div>", unsafe_allow_html=True)

        st.markdown("<div class='history-label'>Yesterday</div>", unsafe_allow_html=True)
        st.markdown("<div class='history-item'>Leave balance report April 2026<br><small>4:45 PM</small></div>", unsafe_allow_html=True)
        st.markdown("<div class='history-item'>Top 5 absent employees this month<br><small>2:30 PM</small></div>", unsafe_allow_html=True)

        st.markdown(
            """
            <div class='sidebar-user'>
                <div>👩🏼‍💼</div>
                <div><strong>Sarah Chen</strong><br><small>HR Manager</small></div>
                <div>⚙</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("</div>", unsafe_allow_html=True)


def render_footer():
    st.markdown(
        """
        <div class="system-footer">
            <span>● System Online</span>
            <span>v2.4.1</span>
            <span>Production</span>
            <span>AI Model: HR-Attend-GPT-4</span>
            <span>Data as of: Apr 21, 2026</span>
            <span>Last sync: 09:50 PM</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
