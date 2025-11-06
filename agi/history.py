# agi/history.py
from __future__ import annotations
import streamlit as st
from datetime import datetime
from .db import fetch_recent_reflections

PAGE_SIZE = 10

def _fmt_dt(val: str) -> str:
    if not val: return ""
    try:
        return datetime.fromisoformat(val.replace("Z","+00:00")).strftime("%b %d, %Y • %I:%M %p")
    except Exception:
        return str(val)

def render_recent_reflections(sb):
    st.markdown("---")
    st.subheader("🕊️ Recent Reflections")

    page = st.session_state.get("page", 0)
    rows, available = fetch_recent_reflections(sb, page, PAGE_SIZE)

    # filters
    if rows:
        with st.container():
            c1, c2, c3 = st.columns([2,1,1])
            q = c1.text_input("Search text (reflection/insight/mantra)", key="recent_q", placeholder="type to filter…")
            theme_opts = ["All"] + sorted({r.get("theme","") for r in rows if r.get("theme")})
            theme_sel = c2.selectbox("Theme", theme_opts, index=0, key="recent_theme")
            mood_sel = None
            if "mood" in available:
                mood_opts = ["All"] + sorted({r.get("mood","") for r in rows if r.get("mood")})
                mood_sel = c3.selectbox("Mood", mood_opts, index=0, key="recent_mood")

            def _match(r):
                if theme_sel and theme_sel != "All" and r.get("theme") != theme_sel: return False
                if mood_sel and mood_sel != "All" and r.get("mood") != mood_sel: return False
                if q:
                    blob = " ".join([
                        str(r.get("reflection_text","")),
                        str(r.get("generated_insight","")),
                        str(r.get("generated_mantra","")),
                        str(r.get("tags","")),
                        str(r.get("tags_raw","")),
                        str(r.get("stillness_note","")),
                    ]).lower()
                    if q.lower() not in blob: return False
                return True
            rows = [r for r in rows if _match(r)]

    if not rows and page == 0:
        st.caption("No reflections yet — your first one will appear here.")
        return

    for r in rows:
        created = _fmt_dt(r.get("created_at",""))
        st.write(f"**{created} — {r.get('theme','')}**")
        st.write(r.get("reflection_text",""))

        meta_bits = []
        if "mood" in available and r.get("mood"): meta_bits.append(f"🧭 {r['mood']}")
        if "stillness_note" in available and r.get("stillness_note"): meta_bits.append(f"🫧 {r['stillness_note']}")
        tags_val = r.get("tags") if "tags" in available and r.get("tags") else r.get("tags_raw")
        if tags_val:
            if isinstance(tags_val, list): meta_bits.append("🏷️ " + ", ".join(map(str, tags_val)))
            else: meta_bits.append("🏷️ " + str(tags_val))
        if meta_bits: st.caption(" • ".join(meta_bits))

        if r.get("generated_insight") or r.get("generated_mantra"):
            with st.expander("Mentor Notes"):
                if r.get("generated_insight"):
                    st.markdown(f"**Insight:** {r['generated_insight']}")
                if r.get("generated_mantra"):
                    st.markdown(f"**Mantra:** _{r['generated_mantra']}_")
        st.markdown("---")

    c1, _, c3 = st.columns(3)
    if c1.button("◀︎ Prev", disabled=(page == 0)):
        st.session_state["page"] = max(0, page - 1); st.rerun()
    if c3.button("Next ▶︎", disabled=(len(rows) < PAGE_SIZE)):
        st.session_state["page"] = page + 1; st.rerun()