# agi/config.py
from __future__ import annotations
import os
import streamlit as st
from typing import Optional

# Breath/tone timing for 4–2–6 pattern (in seconds)
PRESENCE_CYCLE_SEC = 12.0

def init_page():
    st.set_page_config(page_title="AGIcyborg — Reflection", page_icon="🪷", layout="centered")

# --- Secrets / Config (robust) ---
def _get_secret(name: str, default=None):
    try:
        return st.secrets[name]
    except Exception:
        return os.getenv(name, default)

def _first(names: list[str], default=None):
    for n in names:
        v = _get_secret(n)
        if v:
            return v
    return default

def mask(s: Optional[str], *, show_last=4) -> str:
    """
    Safe mask for secrets.
    - Returns '—' if empty
    - Shows only last N characters (default 4)
    - Never shows the prefix
    """
    if not s:
        return "—"

    s = str(s).strip()
    if not s:
        return "—"

    if len(s) <= show_last:
        return "set"

    return f"set (…{s[-show_last:]})"

def mask_url(s: Optional[str], head=8, tail=4) -> str:
    if not s:
        return "—"
    s = str(s)
    if len(s) <= head + tail:
        return s
    return f"{s[:head]}…{s[-tail:]}"

# Expose resolved env keys for reuse
SUPABASE_URL         = _first(["SUPABASE_URL", "SUPABASE_PROJECT_URL"])
SUPABASE_ANON_KEY    = _first(["SUPABASE_ANON_KEY", "SUPABASE_KEY", "SUPABASE_ANON"])
SUPABASE_SERVICE_KEY = _first(["SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE"])
OPENAI_API_KEY       = _first(["OPENAI_API_KEY"])
OPENAI_PROJECT       = _first(["OPENAI_PROJECT", "OPENAI_PROJECT_ID"])  # for sk-proj-* keys