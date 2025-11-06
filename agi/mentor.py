# agi/mentor.py
from __future__ import annotations
import streamlit as st
from streamlit.components.v1 import html as _html

def render_mentor_card(theme: str, insight: str | None, mantra: str | None, anchor_id: str = "mentor_card") -> None:
    theme_safe = (theme or "Clarity").strip().replace(" ", "-")
    mantra_html = f"<p><em>{mantra}</em></p>" if (mantra and mantra.strip()) else ""
    st.markdown(
        f"""
        <a id="{anchor_id}"></a>
        <div class="mentor-card reveal theme-{theme_safe}" role="region" aria-label="Mentor guidance">
          <h4>🕊 Mentor Insight — <span>{theme}</span></h4>
          <p><strong>{(insight or '').strip()}</strong></p>
          {mantra_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
    _html(
        f"""
        <script>
          const el = parent.document.getElementById("{anchor_id}");
          if (el) {{ el.scrollIntoView({{ behavior: "smooth", block: "center" }}); }}
        </script>
        """,
        height=0,
    )