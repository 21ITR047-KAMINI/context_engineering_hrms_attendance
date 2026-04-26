import streamlit as st
import base64


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
    <div class="custom-header">
        <div class="header-left">
            <div class="product-title">HR Attendance Assistant System</div>
        </div>
        <div class="header-right">
            <img src="data:image/png;base64,{logo_base64}" alt="NexusOpt logo" />
        </div>
    </div>
    """

    st.markdown(html, unsafe_allow_html=True)

    
def render_footer():
    st.markdown("""
    <div class="custom-footer">
        © 2026 NexusOpt | AI Attendance Intelligence System | V1.0.0
    </div>
    """, unsafe_allow_html=True)

def render_sidebar():
    with st.sidebar:
        st.markdown("### Workspace")

        if st.button("Clear conversation", use_container_width=True):
            st.session_state.messages = []

        st.markdown("### Starter prompts")
        st.caption("Use these examples to quickly test common HR flows.")
        st.write("- Show today's attendance summary")
        st.write("- Who is on approved leave this week?")
        st.write("- List late arrivals by department")
