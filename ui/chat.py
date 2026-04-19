import streamlit as st
import pandas as pd
import html


def _safe_text(value) -> str:
    return html.escape("" if value is None else str(value))


def render_chat(messages):
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        # USER MESSAGE
        if role == "user":
            st.markdown(
                f"""
                <div class="chat-row user-row">
                    <div class="chat-bubble user-bubble">
                        {_safe_text(content)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            continue

        # ASSISTANT LOADING
        if msg.get("loading", False):
            st.markdown(
                """
                <div class="chat-row bot-row">
                    <div class="thinking-text">Thinking...</div>
                </div>
                """,
                unsafe_allow_html=True
            )
            continue

        # ASSISTANT STRUCTURED RESPONSE
        if isinstance(content, dict):
            explanation = content.get("explanation")
            rows = content.get("rows", [])
            columns = content.get("columns", [])

            # No HTML bubble here, because Streamlit elements won't stay inside it
            with st.container():
                if explanation:
                    st.markdown("### Summary & Insights")
                    st.write(explanation)

                if rows and columns:
                    df = pd.DataFrame(rows, columns=columns)
                    st.markdown("### Data")
                    st.dataframe(df, width="stretch")
            continue

        # ASSISTANT NORMAL TEXT RESPONSE
        st.markdown(
            f"""
            <div class="chat-row bot-row">
                <div class="chat-bubble bot-bubble">
                    {_safe_text(content)}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )