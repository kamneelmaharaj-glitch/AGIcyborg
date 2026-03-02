# agi/debug.py
from __future__ import annotations

import os
import streamlit as st
from typing import Any, Dict, Optional

from agi.auth import S_USER_ID
from agi.config import (
    mask,
    SUPABASE_URL,
    SUPABASE_ANON_KEY,
    SUPABASE_SERVICE_KEY,
    OPENAI_API_KEY,
    OPENAI_PROJECT,
)

def _debug_on() -> bool:
    return (os.getenv("AGI_DEBUG", "0") or "").strip().lower() in ("1", "true", "yes", "on")

def _debug_unlocked() -> bool:
    # local “second key” so DEBUG never shows by accident
    return bool(st.session_state.get("debug_unlock", False))

def render_debug_panel(sb) -> None:
    """
    Sidebar Debug Panel (gated):
      - Requires AGI_DEBUG=1 AND user click “Unlock Debug”
      - Safe masking for secrets
      - Shows E2 reflection_state + last 5 E1 reflection_memory
    """
    if not _debug_on():
        return

    with st.sidebar:
        # Unlock / Lock controls always visible when AGI_DEBUG=1
        if not _debug_unlocked():
            if st.button("🔓 Unlock Debug", key="dbg::unlock"):
                st.session_state["debug_unlock"] = True
                st.rerun()
            return
        else:
            if st.button("🔒 Lock Debug", key="dbg::lock"):
                st.session_state["debug_unlock"] = False
                st.rerun()

    uid = st.session_state.get(S_USER_ID)
    if not uid or not sb:
        st.sidebar.warning("DEBUG: missing user_id or supabase client")
        return

    with st.sidebar.expander("🛠️ Debug", expanded=False):
        col1, col2 = st.columns([1, 1])

        with col1:
            if st.button("🔄 Refresh state", key="dbg::refresh"):
                st.rerun()

        with col2:
            if st.button("🧪 Clear cache", key="dbg::clear_cache"):
                try:
                    st.cache_data.clear()
                except Exception:
                    pass
                try:
                    st.cache_resource.clear()
                except Exception:
                    pass
                st.rerun()

        st.write("user_id:", str(uid))

        st.subheader("Config (masked)")
        st.write("URL:", mask(SUPABASE_URL))
        st.write("Anon key:", "set" if SUPABASE_ANON_KEY else "—")
        st.write("Service key:", "set" if SUPABASE_SERVICE_KEY else "—")
        st.write("OpenAI key:", "set" if OPENAI_API_KEY else "—")
        st.write("OpenAI project:", OPENAI_PROJECT or "—")

    # Main-page debug output (kept outside sidebar expander so it matches your current layout)
    # --- E2 reflection_state ---
    try:
        from agi.persistence.state import fetch_reflection_state
        st_row = fetch_reflection_state(sb, user_id=str(uid)) or {}
    except Exception as e:
        st_row = {}
        st.error(f"E2 fetch error: {str(e)[:160]}")

    st.subheader("E2 reflection_state")
    st.json({
        "last_reflection_at": st_row.get("last_reflection_at"),
        "last_theme": st_row.get("last_theme"),
        "last_mood": st_row.get("last_mood"),
        "last_microstep": st_row.get("last_microstep"),
        "last_presence_stage": st_row.get("last_presence_stage"),
        "presence_drift_hits": st_row.get("presence_drift_hits"),
        "last_presence_day": st_row.get("last_presence_day"),
        "last_presence_updated_at": st_row.get("last_presence_updated_at"),
    })

    # --- E1 reflection_memory ---
    st.subheader("E1 last 5 reflection_memory")
    try:
        res = (
            sb.table("reflection_memory")
            .select("created_at,theme,mood,presence_stage,microstep,silenced")
            .eq("user_id", str(uid))
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        st.table(rows)
    except Exception as e:
        st.error(f"E1 fetch error: {str(e)[:160]}")