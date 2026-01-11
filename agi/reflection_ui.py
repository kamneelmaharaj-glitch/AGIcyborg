# agi/reflection_ui.py
from __future__ import annotations
import streamlit as st


def render_reflection_header(theme: str, prompt_text: str) -> None:
    """
    Minimal calm header for the daily reflection section.

    We let Streamlit draw the outer card border via st.container(border=True)
    and only style the inner content with CSS.
    """
    theme = (theme or "Reflection").strip()
    prompt_text = (prompt_text or "").strip()

    card = st.container(border=True)
    with card:
        st.markdown(
            f"""
            <div class="reflect-header">
              <div class="reflect-header-top">
                <span class="pill">Today’s reflection</span>
                <span class="theme">{theme}</span>
              </div>
              <div class="prompt">{prompt_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )