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

print("MEM ENABLED:", _memory_enabled())

def record_reflection_memory(
    *,
    theme: str,
    mood: str,
    microstep: str,
    insight: Optional[str],
    silenced: bool,
    silence_reason: Optional[str],
    presence_stage: Optional[int] = None,
    supabase=None,  # <-- allow injection
    table_name: str = "reflection_memory",
) -> Dict[str, Any]:
    """
    E1: record-only. Best-effort: never raises to callers.
    Returns a small dict for debug.
    """
    if not _memory_enabled():
        return {"enabled": False, "written": False}

    microstep = (microstep or "").strip()

    # Allow E1 write if silenced, even when microstep is empty
    if not microstep and not silenced:
        return {"enabled": True, "written": False, "reason": "empty_microstep"}

    payload = {
        "theme": (theme or "Reflection").strip() or "Reflection",
        "mood": (mood or "soft").strip() or "soft",
        "presence_stage": presence_stage,
        "microstep": _clip(microstep, 220) if microstep else None,
        "microstep_norm": normalize_microstep(microstep) if microstep else None,
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
            "reason": "insert_failed",
        }

    try:
        res = sb.table(table_name).insert(payload).execute()

        # D-2c: Persist Presence stage into reflection_state (best-effort, non-blocking)
        try:
            uid = _best_effort_user_id()
            if uid and (presence_stage is not None):
                sb.table("reflection_state").upsert(
                    {
                        "user_id": uid,
                        "last_presence_stage": int(presence_stage),
                        "last_presence_updated_at": _now_iso(),
                    },
                    on_conflict="user_id",
                ).execute()
        except Exception:
            pass
        
        data = getattr(res, "data", None)
        err = getattr(res, "error", None)
        return {
            "enabled": True,
            "written": bool(data) and (err is None),
            "error": (str(err)[:200] if err else None),
        }
    except Exception as e:

        print("MEM INSERT res.data:", getattr(res, "data", None))
        print("MEM INSERT res.error:", getattr(res, "error", None))

        return {"enabled": True, "written": False, "error": str(e)[:200], "reason": "insert_failed"}


def fetch_recent_microsteps(
    limit: int = 25,
    *,
    supabase=None,
    table_name: str = "reflection_memory",
) -> List[str]:
    if not _memory_enabled():
        return []

    try:
        sb = supabase or _get_supabase_from_agi_db()
    except Exception:
        return []

    try:
        res = (
            sb.table(table_name)
            .select("microstep")
            .order("created_at", desc=True)
            .limit(int(limit))
            .execute()
        )
        rows = getattr(res, "data", None) or []
        out: List[str] = []
        for r in rows:
            ms = (r.get("microstep") or "").strip()
            if ms:
                out.append(ms)
        return out
    except Exception:
        return []