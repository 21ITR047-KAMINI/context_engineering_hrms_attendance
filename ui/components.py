# ==========================================
# UI COMPONENTS (Reusable)
# ==========================================

import streamlit as st
import pandas as pd


# ------------------------------------------
# MESSAGE BUBBLES
# ------------------------------------------
def user_message(text: str):
    st.markdown(
        f'<div class="user-msg">{text}</div>',
        unsafe_allow_html=True
    )


def bot_message(text: str):
    st.markdown(
        f'<div class="bot-msg">{text}</div>',
        unsafe_allow_html=True
    )


# ------------------------------------------
# TABLE RENDERER
# ------------------------------------------
def render_table(rows, columns):
    """
    Render structured data as dataframe
    """
    if not rows:
        st.warning("No data available")
        return

    df = pd.DataFrame(rows, columns=columns)
    st.dataframe(df, use_container_width=True)


# ------------------------------------------
# ANALYSIS BLOCK
# ------------------------------------------
def render_analysis(explanation: str):
    """
    Display AI explanation nicely
    """
    st.markdown("Analysis")
    st.write(explanation)


# ------------------------------------------
# METRIC CARDS
# ------------------------------------------
def render_metrics(rows):
    """
    Basic metrics from result
    """
    if not rows:
        return

    total = len(rows)

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Total Records", total)

    with col2:
        st.metric("Data Loaded", "Yes")


# ------------------------------------------
# LOADING SPINNER
# ------------------------------------------
def show_loader():
    return st.spinner("Processing query...")


# ------------------------------------------
# ERROR DISPLAY
# ------------------------------------------
def show_error(message: str):
    st.error(message)


# ------------------------------------------
# SUCCESS MESSAGE
# ------------------------------------------
def show_success(message: str):
    st.success(message)


# ------------------------------------------
# EMPTY STATE
# ------------------------------------------
def show_empty():
    st.info("No results found for your query.")