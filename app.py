# ==========================================
# HR Attendance AI - Main App
# ==========================================

import streamlit as st
import time
from graph.graph_builder import build_graph

from ui.layout import render_header, render_footer, render_sidebar
from ui.chat import render_chat
from ui.styles import inject_custom_css


st.set_page_config(page_title="HR Attendance AI Assistant", layout="wide")


@st.cache_resource
def load_graph():
    return build_graph()


def process_query(graph, query):
    try:
        start_time = time.time()
        response = graph.invoke({"query": query})
        latency = round(time.time() - start_time, 2)
        result = response.get("response", "No response generated")
        return result, latency
    except Exception as e:
        return f"Error: {str(e)}", 0


def _demo_response(user_input: str):
    return {
        "title": "Attendance Summary — Last 30 Days",
        "subtitle": "10:14 AM · AI-generated analysis",
        "explanation": "Here's a comprehensive breakdown of attendance across all departments. Overall performance is trending positively.",
        "metrics": [
            {"value": "87.4%", "label": "Present Rate", "sub": "+2.1% vs last month", "delta": "↑ +2.1%", "tone": "positive"},
            {"value": "7.2%", "label": "Absent Rate", "sub": "-0.8% vs last month", "delta": "↓ -0.8%", "tone": "negative"},
            {"value": "5.4%", "label": "On Leave", "sub": "+0.3% vs last month", "delta": "→ +0.3%", "tone": "neutral"},
        ],
        "query": user_input,
    }


def init_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": {
                    "title": "Attendance Summary — Last 30 Days",
                    "subtitle": "10:14 AM · AI-generated analysis",
                    "explanation": "Here's a comprehensive breakdown of attendance across all departments from March 24 to April 21, 2026. Overall performance is trending positively with a 2.1% improvement month-over-month.",
                    "metrics": [
                        {"value": "87.4%", "label": "Present Rate", "sub": "+2.1% vs last month", "delta": "↑ +2.1%", "tone": "positive"},
                        {"value": "7.2%", "label": "Absent Rate", "sub": "-0.8% vs last month", "delta": "↓ -0.8%", "tone": "negative"},
                        {"value": "5.4%", "label": "On Leave", "sub": "+0.3% vs last month", "delta": "→ +0.3%", "tone": "neutral"},
                    ],
                },
            }
        ]

    if "pending_query" not in st.session_state:
        st.session_state.pending_query = None

    if "is_processing" not in st.session_state:
        st.session_state.is_processing = False


def handle_user_input(user_input: str):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.messages.append({"role": "assistant", "content": "Thinking...", "loading": True})
    st.session_state.pending_query = user_input
    st.session_state.is_processing = True
    st.rerun()


def handle_pending_query(graph):
    if st.session_state.pending_query and st.session_state.is_processing:
        query = st.session_state.pending_query
        _, latency = process_query(graph, query)

        if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant" and st.session_state.messages[-1].get("loading"):
            st.session_state.messages.pop()

        st.session_state.messages.append({"role": "assistant", "content": _demo_response(query), "latency": latency})

        st.session_state.pending_query = None
        st.session_state.is_processing = False
        st.rerun()


def render_prompt_chips():
    st.markdown(
        """
        <div style='display:flex; gap:8px; flex-wrap:wrap; margin:8px 0 14px;'>
            <span style='padding:6px 12px; background:#fff; border:1px solid #e5e7eb; border-radius:999px;'>Show attendance summary for last 30 days</span>
            <span style='padding:6px 12px; background:#fff; border:1px solid #e5e7eb; border-radius:999px;'>Which department has the highest absenteeism?</span>
            <span style='padding:6px 12px; background:#fff; border:1px solid #e5e7eb; border-radius:999px;'>List employees on leave this week</span>
            <span style='padding:6px 12px; background:#fff; border:1px solid #e5e7eb; border-radius:999px;'>Compare Q1 vs Q2 attendance trends</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main():
    inject_custom_css()
    render_header()
    render_sidebar()

    init_session_state()
    graph = load_graph()

    with st.container():
        render_chat(st.session_state.messages)

    render_prompt_chips()

    user_input = st.chat_input("Ask about attendance, leave, absenteeism, or employee insights…", disabled=st.session_state.is_processing)

    if user_input and not st.session_state.is_processing:
        handle_user_input(user_input)

    if st.session_state.pending_query and st.session_state.is_processing:
        with st.spinner("Processing..."):
            handle_pending_query(graph)

    render_footer()


if __name__ == "__main__":
    main()
