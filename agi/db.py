# agi/db.py
from __future__ import annotations
import streamlit as st
from supabase import create_client, Client
from .config import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY

def get_client() -> Client:
    if not SUPABASE_URL:
        st.error("Missing `SUPABASE_URL`. Configure in .streamlit/secrets.toml or env.")
        st.stop()
    key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
    if not key:
        st.error("Missing Supabase key. Provide `SUPABASE_SERVICE_KEY` or `SUPABASE_ANON_KEY`.")
        st.stop()
    return create_client(SUPABASE_URL, key)

def fetch_prompts(sb: Client) -> list[dict]:
    try:
        res = sb.table("reflection_prompts").select("id, theme, prompt, active").order("theme").execute()
        return [r for r in (res.data or []) if r.get("active", True)]
    except Exception as e:
        st.error(f"Could not load prompts: {e}")
        return []

def insert_presence_session(sb: Client, duration_sec: int, presence_score: float):
    sb.table("presence_sessions").insert({
        "duration_sec": duration_sec,
        "presence_score": presence_score,
        "source": "app",
    }).execute()

def insert_reflection_with_fallbacks(sb: Client, base_row: dict, optional_fields: dict, energy_fields: dict):
    full_row    = {**base_row, **optional_fields, **energy_fields}
    opt_row     = {**base_row, **optional_fields}
    minimal_row = {**base_row}
    def _try(payload): return sb.table("user_reflections").insert(payload).execute()
    try:
        return _try(full_row)
    except Exception:
        try:
            return _try(opt_row)
        except Exception:
            return _try(minimal_row)

def fetch_recent_reflections(sb: Client, page: int, page_size: int, want_optional: bool = True):
    base_cols = ["created_at","theme","reflection_text","generated_insight","generated_mantra"]
    optional_cols = ["tags","tags_raw","mood","stillness_note"]
    cols = base_cols + (optional_cols if want_optional else [])
    try:
        res = (
            sb.table("user_reflections")
              .select(", ".join(cols))
              .order("created_at", desc=True)
              .range(page * page_size, page * page_size + page_size - 1)
              .execute()
        )
        return (res.data or []), set(cols)
    except Exception:
        # retry base only
        res = (
            sb.table("user_reflections")
              .select(", ".join(base_cols))
              .order("created_at", desc=True)
              .range(page * page_size, page * page_size + page_size - 1)
              .execute()
        )
        return (res.data or []), set(base_cols)