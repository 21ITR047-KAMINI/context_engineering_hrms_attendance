# ==========================================
# HR Attendance AI - Main App
# ==========================================

import streamlit as st
import time
from graph.graph_builder import build_graph

from ui.layout import render_header, render_footer, render_sidebar
from ui.chat import render_chat
from ui.styles import inject_custom_css


st.set_page_config(
    page_title="HR Attendance AI Assistant",
    layout="wide"
)


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


def init_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "pending_query" not in st.session_state:
        st.session_state.pending_query = None

    if "is_processing" not in st.session_state:
        st.session_state.is_processing = False


def handle_user_input(user_input: str):
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

    st.session_state.messages.append({
        "role": "assistant",
        "content": "Thinking...",
        "loading": True
    })

    st.session_state.pending_query = user_input
    st.session_state.is_processing = True
    st.rerun()


def handle_pending_query(graph):
    if st.session_state.pending_query and st.session_state.is_processing:
        query = st.session_state.pending_query
        response, latency = process_query(graph, query)

        if (
            st.session_state.messages
            and st.session_state.messages[-1]["role"] == "assistant"
            and st.session_state.messages[-1].get("loading")
        ):
            st.session_state.messages.pop()

        st.session_state.messages.append({
            "role": "assistant",
            "content": response,
            "latency": latency
        })

        st.session_state.pending_query = None
        st.session_state.is_processing = False
        st.rerun()


def main():
    inject_custom_css()
    render_header()
    render_sidebar()

    init_session_state()
    graph = load_graph()

    # 1. render current chat first
    chat_container = st.container()
    with chat_container:
        render_chat(st.session_state.messages)

    # 2. then show input
    user_input = st.chat_input(
        "How can I help you today?",
        disabled=st.session_state.is_processing
    )

    if user_input and not st.session_state.is_processing:
        handle_user_input(user_input)

    # 3. IMPORTANT: process only after UI already rendered
    if st.session_state.pending_query and st.session_state.is_processing:
        with st.spinner("Processing..."):
            handle_pending_query(graph)

    render_footer()


if __name__ == "__main__":
    main()