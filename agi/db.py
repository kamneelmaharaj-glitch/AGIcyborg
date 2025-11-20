# agi/db.py
from __future__ import annotations
import streamlit as st
from supabase import create_client, Client
from typing import Optional
from .config import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY

@st.cache_resource 
def get_client() -> Client:
    if not SUPABASE_URL:
        st.error("Missing `SUPABASE_URL`. Configure in .streamlit/secrets.toml or env.")
        st.stop()
    key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
    if not key:
        st.error("Missing Supabase key. Provide `SUPABASE_SERVICE_KEY` or `SUPABASE_ANON_KEY`.")
        st.stop()
    return create_client(SUPABASE_URL, key)

def upsert_profile(sb: Client, user_id, email: str, display_name: Optional[str]):
    try:
        sb.table("profiles").upsert({
            "id": str(user_id),
            "email": email,
            "display_name": display_name
        }, on_conflict="id").execute()
    except Exception:
        pass

def upsert_reflection_vector(sb, *, user_id: str, theme: str | None, energy: float | None, presence: float | None):
    try:
        sb.table("user_reflection_vectors").insert({
            "user_id": user_id,
            "theme": theme,
            "energy_score": energy,
            "presence_score": presence
        }).execute()
    except Exception:
        # swallow or log if needed
        pass

def fetch_prompts(sb: Client) -> list[dict]:
    try:
        res = sb.table("reflection_prompts").select("id, theme, prompt, active").order("theme").execute()
        return [r for r in (res.data or []) if r.get("active", True)]
    except Exception as e:
        st.error(f"Could not load prompts: {e}")
        return []

def insert_presence_session(sb: Client, duration_sec: int, presence_score: float, user_id: Optional[str] = None):
    payload = {
        "duration_sec": duration_sec,
        "presence_score": presence_score,
        "source": "app",
    }
    if user_id:
        payload["user_id"] = user_id
    sb.table("presence_sessions").insert(payload).execute()

def insert_reflection_with_fallbacks(sb: Client, base_row: dict, optional_fields: dict, energy_fields: dict, user_id: Optional[str] = None):
    base = dict(base_row)
    if user_id:
        base["user_id"] = user_id

    full_row    = {**base, **optional_fields, **energy_fields}
    opt_row     = {**base, **optional_fields}
    minimal_row = {**base}

    def _try(payload): return sb.table("user_reflections").insert(payload).execute()
    try:
        return _try(full_row)
    except Exception:
        try:
            return _try(opt_row)
        except Exception:
            return _try(minimal_row)

def fetch_recent_reflections(sb: Client, page: int, page_size: int, user_id: Optional[str] = None, want_optional: bool = True):
    base_cols = ["created_at","theme","reflection_text","generated_insight","generated_mantra"]
    optional_cols = ["tags","tags_raw","mood","stillness_note"]
    cols = base_cols + (optional_cols if want_optional else [])

    q = sb.table("user_reflections").select(", ".join(cols))
    if user_id:
        q = q.eq("user_id", user_id)

    try:
        res = q.order("created_at", desc=True).range(page * page_size, page * page_size + page_size - 1).execute()
        return (res.data or []), set(cols)
    except Exception:
        res = sb.table("user_reflections").select(", ".join(base_cols))
        if user_id:
            res = res.eq("user_id", user_id)
        res = res.order("created_at", desc=True).range(page * page_size, page * page_size + page_size - 1).execute()
        return (res.data or []), set(base_cols)
    
def save_followup_ai(sb, *, user_id: str, reflection_id: str | None,
                     theme: str | None, note: str | None,
                     insight: str | None, microstep: str | None,
                     meta: dict | None = None):
    payload = {
        "user_id": user_id,
        "reflection_id": reflection_id,
        "theme": theme,
        "followup_note": note,
        "insight": insight,
        "microstep": microstep,
        "meta": meta or {},
    }
    return sb.table("user_followup_ai").insert(payload).execute()

def list_followups(sb, *, user_id: str, limit: int = 20, offset: int = 0):
    return (
        sb.table("user_followup_ai")
          .select("*")
          .eq("user_id", user_id)
          .order("created_at", desc=True)
          .range(offset, offset + limit - 1)
          .execute()
    )