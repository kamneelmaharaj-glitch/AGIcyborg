# agi/memory.py
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone


def _env_truthy(name: str, default: str = "0") -> bool:
    v = (os.getenv(name, default) or "").strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def _memory_enabled() -> bool:
    return _env_truthy("AGI_MEMORY_ENABLED", "0")


def normalize_microstep(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^\w\s]", "", s)  # remove punctuation
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _clip(s: Optional[str], n: int) -> Optional[str]:
    if s is None:
        return None
    s = s.strip()
    return s if len(s) <= n else (s[:n] + "…")

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _best_effort_user_id() -> Optional[str]:
    """
    Try to get user_id without forcing callers to pass it.
    Works in Streamlit runtime; safely returns None otherwise.
    """
    try:
        import streamlit as st  # type: ignore
        from agi.auth import S_USER_ID  # type: ignore
        uid = st.session_state.get(S_USER_ID)
        return str(uid).strip() if uid else None
    except Exception:
        return None
    
def _get_supabase_from_agi_db():
    """
    Attempts to obtain a Supabase client from agi.db using common patterns.

    Supported:
      - agi.db.get_supabase()
      - agi.db.get_sb()
      - agi.db.get_client()
      - agi.db.supabase (global)
      - agi.db.sb       (global)
    """
    try:
        import agi.db as db  # type: ignore
    except Exception as e:
        raise RuntimeError(f"Could not import agi.db: {e}") from e

    # preferred callables
    for fn_name in ("get_supabase", "get_sb", "get_client"):
        fn = getattr(db, fn_name, None)
        if callable(fn):
            return fn()

    # common global singletons
    for attr in ("supabase", "sb"):
        client = getattr(db, attr, None)
        if client is not None:
            return client

    raise RuntimeError(
        "No Supabase accessor found in agi.db. Expected one of: "
        "get_supabase(), get_sb(), get_client(), or globals supabase/sb."
    )


def record_reflection_memory(
    *,
    theme: str,
    mood: str,
    microstep: str,
    insight: Optional[str],
    silenced: bool,
    silence_reason: Optional[str],
    presence_stage: Optional[int] = None,
    supabase=None,
    table_name: str = "reflection_memory",
) -> Dict[str, Any]:
    """
    E1: record-only. Best-effort: never raises to callers.

    DB constraints assumed (based on your schema):
      - microstep        NOT NULL
      - microstep_norm   NOT NULL
      - user_id          exists (you want to require it for integrity)

    Behavior:
      - Non-silenced + empty microstep -> no write
      - Silenced + empty microstep -> write with microstep="" / microstep_norm=""
      - Missing user_id -> no write (integrity)
    """
    if not _memory_enabled():
        return {"enabled": False, "written": False}

    # --- require uid for integrity ---
    uid = _best_effort_user_id()  # may be None outside Streamlit
    if not uid:
        return {"enabled": True, "written": False, "reason": "missing_user_id"}

    ms = (microstep or "").strip()

    # Non-silence days require a real microstep
    if not ms and not silenced:
        return {"enabled": True, "written": False, "reason": "empty_microstep"}

    # Silence days may write even if microstep empty — keep NOT NULL happy
    if silenced and not ms:
        ms = ""

    ms_norm = normalize_microstep(ms)  # will be "" if ms == ""

    payload: Dict[str, Any] = {
        "user_id": str(uid),
        "theme": (theme or "Reflection").strip() or "Reflection",
        "mood": (mood or "soft").strip() or "soft",
        "presence_stage": presence_stage,
        # IMPORTANT: always NOT NULL
        "microstep": _clip(ms, 220) if ms is not None else "",
        "microstep_norm": _clip(ms_norm, 220) if ms_norm is not None else "",
        "insight": _clip(insight, 420) if insight else None,
        "silenced": bool(silenced),
        "silence_reason": _clip(silence_reason, 120) if silence_reason else None,
    }

    try:
        sb = supabase or _get_supabase_from_agi_db()
    except Exception as e:
        return {
            "enabled": True,
            "written": False,
            "error": str(e)[:200],
            "reason": "no_supabase",
        }

    try:
        res = sb.table(table_name).insert(payload).execute()
        data = getattr(res, "data", None)
        err = getattr(res, "error", None)
        return {
            "enabled": True,
            "written": bool(data) and (err is None),
            "error": (str(err)[:200] if err else None),
        }
    except Exception as e:
        return {
            "enabled": True,
            "written": False,
            "error": str(e)[:200],
            "reason": "insert_failed",
        }