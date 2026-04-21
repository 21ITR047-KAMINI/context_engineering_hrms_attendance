import html
import streamlit as st


def _safe_text(value) -> str:
    return html.escape("" if value is None else str(value))


def _render_kpi_cards(metrics):
    st.markdown("<div class='kpi-grid'>", unsafe_allow_html=True)
    for metric in metrics:
        tone = metric.get("tone", "neutral")
        st.markdown(
            f"""
            <div class='kpi-card {tone}'>
                <div class='kpi-delta'>{_safe_text(metric.get("delta", ""))}</div>
                <div class='kpi-value'>{_safe_text(metric.get("value", ""))}</div>
                <div class='kpi-label'>{_safe_text(metric.get("label", ""))}</div>
                <div class='kpi-sub'>{_safe_text(metric.get("sub", ""))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def render_chat(messages):
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "user":
            st.markdown(
                f"""
                <div class="chat-row user-row">
                    <div class="chat-bubble user-bubble">
                        {_safe_text(content)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            continue

        if msg.get("loading", False):
            st.markdown(
                """
                <div class="chat-row bot-row">
                    <div class="thinking-text">Thinking...</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            continue

        if isinstance(content, dict):
            title = content.get("title", "Attendance Summary")
            subtitle = content.get("subtitle", "AI-generated analysis")
            explanation = content.get("explanation", "")
            metrics = content.get("metrics", [])

            st.markdown(
                f"""
                <div class='assistant-card'>
                    <div class='assistant-head'>
                        <div class='assistant-title'>{_safe_text(title)}</div>
                        <div class='assistant-sub'>{_safe_text(subtitle)}</div>
                    </div>
                    <div class='assistant-body'>{_safe_text(explanation)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if metrics:
                _render_kpi_cards(metrics)
            continue

        st.markdown(
            f"""
            <div class="chat-row bot-row">
                <div class="chat-bubble bot-bubble">
                    {_safe_text(content)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
