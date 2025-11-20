# agi/deepen_ui.py
from __future__ import annotations
import streamlit as st

def render_deepen_ai_card(theme: str, insight: str, microstep: str) -> None:
    box = st.container(border=True)
    with box:
        st.caption(f"Deepen Mentor — {theme}")
        st.write(f"**Insight:** {insight}")
        st.write(f"**Micro-step:** {microstep}")