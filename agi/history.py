# agi/history.py
from __future__ import annotations
import streamlit as st
from datetime import datetime, timedelta

PAGE_SIZE = 10

def _fmt_dt(val: str) -> str:
    if not val:
        return ""
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00")).strftime("%b %d, %Y • %I:%M %p")
    except Exception:
        return str(val)

def render_recent_reflections(sb, days: int = 45, theme: str | None = None):
    from agi.auth import S_USER_ID

    uid = st.session_state.get(S_USER_ID)
    if not uid:
        return

    start = (datetime.utcnow() - timedelta(days=days)).isoformat()

    base_cols = ["created_at","theme","reflection_text","generated_insight","generated_mantra"]
    optional_cols = ["tags","tags_raw","mood","stillness_note"]
    cols = base_cols + optional_cols

    # Keep page index scoped to current filter combo
    page_key = f"hist_page::{uid}::{days}::{theme or 'ALL'}"
    page = st.session_state.get(page_key, 0)

    q = sb.table("user_reflections").select(", ".join(cols)).eq("user_id", uid).gte("created_at", start)
    if theme:
        q = q.eq("theme", theme)
    try:
        res = q.order("created_at", desc=True).range(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE - 1).execute()
        rows = res.data or []
        available = set(cols)
    except Exception:
        res = sb.table("user_reflections").select(", ".join(base_cols)).eq("user_id", uid).gte("created_at", start)
        if theme: res = res.eq("theme", theme)
        res = res.order("created_at", desc=True).range(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE - 1).execute()
        rows = res.data or []
        available = set(base_cols)

    st.markdown("---")
    st.subheader("🕊️ Recent Reflections")

    # Client-side quick filters inside this range (optional search)
    if rows:
        c1, c2 = st.columns([2, 1])
        qtext = c1.text_input("Search text", key=f"recent_q::{page_key}", placeholder="filter in this view…")
        theme_disp = theme or "All"
        c2.caption(f"Range: last {days} days • Theme: {theme_disp}")

        def _match(r):
            if qtext:
                blob = " ".join([
                    str(r.get("reflection_text","")),
                    str(r.get("generated_insight","")),
                    str(r.get("generated_mantra","")),
                    str(r.get("tags","")),
                    str(r.get("tags_raw","")),
                    str(r.get("stillness_note","")),
                ]).lower()
                if qtext.lower() not in blob:
                    return False
            return True

        rows = [r for r in rows if _match(r)]

    if not rows and page == 0:
        st.caption("No reflections in this range yet.")
    else:
        for r in rows:
            created = _fmt_dt(r.get("created_at", ""))
            st.write(f"**{created} — {r.get('theme','')}**")
            st.write(r.get("reflection_text", ""))

            meta_bits = []
            if "mood" in available and r.get("mood"): meta_bits.append(f"🧭 {r['mood']}")
            if "stillness_note" in available and r.get("stillness_note"): meta_bits.append(f"🫧 {r['stillness_note']}")
            tags_val = r.get("tags") if "tags" in available else (r.get("tags_raw") if "tags_raw" in available else None)
            if tags_val:
                if isinstance(tags_val, list): meta_bits.append("🏷️ " + ", ".join(map(str, tags_val)))
                else: meta_bits.append("🏷️ " + str(tags_val))
            if meta_bits: st.caption(" • ".join(meta_bits))

            if r.get("generated_insight") or r.get("generated_mantra"):
                with st.expander("Mentor Notes"):
                    if r.get("generated_insight"): st.markdown(f"**Insight:** {r['generated_insight']}")
                    if r.get("generated_mantra"): st.markdown(f"**Mantra:** _{r['generated_mantra']}_")
            st.markdown("---")

        c1, _, c3 = st.columns(3)
        if c1.button("◀︎ Prev", disabled=(page == 0), key=f"prev::{page_key}"):
            st.session_state[page_key] = max(0, page - 1); st.rerun()
        if c3.button("Next ▶︎", disabled=(len(rows) < PAGE_SIZE), key=f"next::{page_key}"):
            st.session_state[page_key] = page + 1; st.rerun()