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
            HR Attendance AI Assistant
        </div>
        <div class="header-right">
            <img src="data:image/png;base64,{logo_base64}" style="height:140px; width:auto;" />
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
        st.markdown("## Controls")

        if st.button("Clear Chat"):
            st.session_state.messages = []

        st.markdown("### Example Queries")
        st.write("- Show attendance")
        st.write("- Who is on leave?")