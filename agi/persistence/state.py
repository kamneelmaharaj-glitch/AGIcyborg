"""
User continuity & lifecycle state.

This module manages long-lived per-user state such as:
- last reflection time
- last meaningful action
- continuity counters
- presence stage continuity (0–3/4) + drift hits

This layer is persistence-aware but behavior-driven.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None:
            return default
        if isinstance(v, bool):
            return default
        return int(v)
    except Exception:
        return default


def _safe_date_str(v: Any, default: Optional[str] = None) -> Optional[str]:
    """
    Accepts:
      - 'YYYY-MM-DD' string
      - datetime/date objects (best-effort)
    Returns:
      - 'YYYY-MM-DD' or default
    """
    try:
        if v is None:
            return default
        if isinstance(v, str):
            s = v.strip()
            if len(s) >= 10:
                return s[:10]
            return default
        # datetime/date-like
        if hasattr(v, "isoformat"):
            return str(v.isoformat())[:10]
        return default
    except Exception:
        return default


# -------------------------------------------------------------------
# Reads
# -------------------------------------------------------------------

def fetch_reflection_state(
    supabase,
    *,
    user_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Best-effort read of the per-user reflection_state row.
    Returns the row dict or None. Never raises.
    """
    if not (supabase and user_id):
        return None

    try:
        res = (
            supabase.table("reflection_state")
            .select(
                "user_id,"
                "last_reflection_at,last_theme,last_mood,"
                "last_microstep,last_microstep_at,"
                "last_meaningful_action,last_action_at,"
                "reflection_count,updated_at,"
                "last_silenced,last_silence_reason,"
                "last_presence_stage,presence_drift_hits,"
                "last_presence_updated_at,last_presence_day"
            )
            .eq("user_id", str(user_id))
            .limit(1)
            .execute()
        )

        data = getattr(res, "data", None)
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict) and data:
            return data
        return None
    except Exception:
        return None


# -------------------------------------------------------------------
# Writes (Reflection continuity)
# -------------------------------------------------------------------

def upsert_reflection_state(
    supabase,
    *,
    user_id: str,
    theme: Optional[str],
    mood: Optional[str],
    microstep: Optional[str],
    last_meaningful_action: Optional[str],
    silenced: bool = False,
    silence_reason: Optional[str] = None,
    reflection_at: Optional[datetime] = None,
    microstep_at: Optional[datetime] = None,
    action_at: Optional[datetime] = None,
    increment_reflection_count: bool = True,
) -> Dict[str, Any]:
    """
    Upserts a single per-user continuity row in public.reflection_state.
    Assumes:
      - reflection_state.user_id is PRIMARY KEY
      - updated_at has default now() but we also set it explicitly
    """
    if not (supabase and user_id):
        return {"written": False, "reason": "missing_supabase_or_user"}

    now = _utcnow()
    reflection_at = reflection_at or now

    microstep = (microstep or "").strip() or None
    last_meaningful_action = (last_meaningful_action or "").strip() or None

    # default: treat microstep/action as happening "now" if provided
    if microstep and microstep_at is None:
        microstep_at = now
    if last_meaningful_action and action_at is None:
        action_at = now

    payload: Dict[str, Any] = {
        "user_id": str(user_id),
        "last_reflection_at": reflection_at.isoformat(),
        "last_theme": theme,
        "last_mood": mood,
        "last_silenced": bool(silenced),
        "last_silence_reason": silence_reason,
        "updated_at": now.isoformat(),
    }

    # Only write these if we have values (avoid overwriting with null)
    if microstep:
        payload["last_microstep"] = microstep
        payload["last_microstep_at"] = (microstep_at or now).isoformat()

    if last_meaningful_action:
        payload["last_meaningful_action"] = last_meaningful_action
        payload["last_action_at"] = (action_at or now).isoformat()

    try:
        res = (
            supabase.table("reflection_state")
            .upsert(payload, on_conflict="user_id")
            .execute()
        )
    except Exception as e:
        return {"written": False, "payload": payload, "error": str(e)[:180]}

    # Optional: increment reflection_count via RPC for correctness under concurrency
    if increment_reflection_count:
        try:
            supabase.rpc("increment_reflection_count", {"p_user_id": str(user_id)}).execute()
        except Exception:
            pass

    return {"written": True, "payload": payload, "data": getattr(res, "data", None)}


# -------------------------------------------------------------------
# Writes (Presence continuity) — D2
# -------------------------------------------------------------------

def upsert_presence_state(
    supabase,
    *,
    user_id: str,
    last_presence_stage: int,
    presence_drift_hits: int,
    last_presence_day: str,  # "YYYY-MM-DD"
    presence_updated_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Upsert Presence continuity into reflection_state.
    Best-effort: never raises.
    """
    if not (supabase and user_id):
        return {"written": False, "reason": "missing_supabase_or_user"}

    now = presence_updated_at or _utcnow()
    day = _safe_date_str(last_presence_day, default=now.date().isoformat())

    payload: Dict[str, Any] = {
        "user_id": str(user_id),
        "last_presence_stage": _safe_int(last_presence_stage, 0),
        "presence_drift_hits": _safe_int(presence_drift_hits, 0),
        "last_presence_day": day,
        "last_presence_updated_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }

    try:
        res = (
            supabase.table("reflection_state")
            .upsert(payload, on_conflict="user_id")
            .execute()
        )
        return {"written": True, "payload": payload, "data": getattr(res, "data", None)}
    except Exception as e:
        return {"written": False, "payload": payload, "error": str(e)[:180]}


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def get_presence_prev(
    state_row: Optional[Dict[str, Any]],
    *,
    default_stage: int = 0,
    default_drift: int = 0,
) -> Tuple[int, int]:
    """
    Convenience helper: extract previous stage + drift hits from a state row.
    """
    if not state_row:
        return default_stage, default_drift

    stage_prev = _safe_int(state_row.get("last_presence_stage"), default_stage)
    drift_prev = _safe_int(state_row.get("presence_drift_hits"), default_drift)
    return stage_prev, drift_prev

# -------------------------------------------------------------------
# Option C: Coherence (E1 -> E2 single-writer) + Repair
# -------------------------------------------------------------------

def sync_reflection_state_from_event(
    supabase,
    *,
    user_id: str,
    # E1 event fields (what you just wrote to reflection_memory)
    theme: Optional[str],
    mood: Optional[str],
    microstep: Optional[str],
    insight: Optional[str],  # not stored in E2, but kept for possible future
    silenced: bool,
    silence_reason: Optional[str],
    presence_stage_final: Optional[int],
    presence_drift_hits_new: Optional[int] = None,
    occurred_at: Optional[datetime] = None,
    # if you have a notion of "meaningful action", pass it here
    last_meaningful_action: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Canonical E2 sync.

    Call this ONCE per reflection event, immediately after E1 insert succeeds.
    This prevents multi-writer drift and guarantees reflection_state is coherent.

    Best-effort: never raises.
    """
    if not (supabase and user_id):
        return {"written": False, "reason": "missing_supabase_or_user"}

    now = _utcnow()
    occurred_at = occurred_at or now

    # --- Idempotency guard: never rewind state on out-of-order events ---
    try:
        cur = (
            supabase.table("reflection_state")
            .select("last_reflection_at")
            .eq("user_id", str(user_id))
            .maybe_single()
            .execute()
        )
        current_ts = (getattr(cur, "data", None) or {}).get("last_reflection_at")
        if current_ts:
            current_dt = datetime.fromisoformat(str(current_ts).replace("Z", "+00:00"))
            if current_dt.tzinfo is None:
                current_dt = current_dt.replace(tzinfo=timezone.utc)
            if occurred_at <= current_dt:
                return {
                    "written": False,
                    "reason": "stale_event_skipped",
                    "event_at": occurred_at.isoformat(),
                    "current_at": current_dt.isoformat(),
                }
    except Exception:
        # best-effort only; never block the write if guard can't read
        pass

    microstep = (microstep or "").strip() or None
    last_meaningful_action = (last_meaningful_action or "").strip() or None

    payload: Dict[str, Any] = {
        "user_id": str(user_id),
        "last_reflection_at": occurred_at.isoformat(),
        "last_theme": theme,
        "last_mood": mood,
        "last_silenced": bool(silenced),
        "last_silence_reason": silence_reason,
        "updated_at": now.isoformat(),
    }

    # Reflection continuity
    if microstep:
        payload["last_microstep"] = microstep
        payload["last_microstep_at"] = occurred_at.isoformat()

    if last_meaningful_action:
        payload["last_meaningful_action"] = last_meaningful_action
        payload["last_action_at"] = occurred_at.isoformat()

    # Presence continuity (D2)
    if presence_stage_final is not None:
        payload["last_presence_stage"] = _safe_int(presence_stage_final, 0)
        payload["last_presence_updated_at"] = occurred_at.isoformat()
        payload["last_presence_day"] = occurred_at.date().isoformat()

    if presence_drift_hits_new is not None:
        payload["presence_drift_hits"] = _safe_int(presence_drift_hits_new, 0)

    try:
        res = (
            supabase.table("reflection_state")
            .upsert(payload, on_conflict="user_id")
            .execute()
        )
    except Exception as e:
        return {"written": False, "payload": payload, "error": str(e)[:180]}

    # reflection_count increment (optional, safe)
    try:
        supabase.rpc("increment_reflection_count", {"p_user_id": str(user_id)}).execute()
    except Exception:
        pass

    return {"written": True, "payload": payload, "data": getattr(res, "data", None)}


def rebuild_reflection_state_from_memory(
    supabase,
    *,
    user_id: str,
    lookback: int = 50,
    table_name: str = "reflection_memory",
) -> Dict[str, Any]:
    """
    Repair/backfill: rebuild the *current* reflection_state fields
    from recent reflection_memory rows.

    Use this if you ever suspect drift, or after schema/logic changes.
    Best-effort: never raises.
    """
    if not (supabase and user_id):
        return {"rebuilt": False, "reason": "missing_supabase_or_user"}

    try:
        res = (
            supabase.table(table_name)
            .select("created_at,theme,mood,microstep,silenced,silence_reason,presence_stage")
            .eq("user_id", str(user_id))
            .order("created_at", desc=True)
            .limit(int(lookback))
            .execute()
        )
        rows = getattr(res, "data", None) or []
        if not rows:
            return {"rebuilt": False, "reason": "no_memory_rows"}
    except Exception as e:
        return {"rebuilt": False, "reason": "read_failed", "error": str(e)[:180]}

    # Latest event is source-of-truth for "last_*"
    latest = rows[0] or {}
    created_at = latest.get("created_at")
    occurred_at = None
    if isinstance(created_at, str) and created_at:
        try:
            occurred_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=timezone.utc)
            occurred_at = occurred_at.astimezone(timezone.utc)
        except Exception:
            occurred_at = _utcnow()
    else:
        occurred_at = _utcnow()

    theme = latest.get("theme")
    mood = latest.get("mood")
    microstep = latest.get("microstep")
    silenced = bool(latest.get("silenced", False))
    silence_reason = latest.get("silence_reason")
    presence_stage = latest.get("presence_stage")

    # Drift hits cannot be reconstructed from E1
    # Preserve existing E2 value by NOT incrementing during rebuild
    existing = fetch_reflection_state(supabase, user_id=str(user_id)) or {}

    return sync_reflection_state_from_event(
        supabase,
        user_id=str(user_id),
        theme=theme,
        mood=mood,
        microstep=microstep,
        insight=None,
        silenced=silenced,
        silence_reason=silence_reason,
        presence_stage_final=_safe_int(presence_stage, 0) if presence_stage is not None else None,
        presence_drift_hits_new=0,
        occurred_at=occurred_at,
        last_meaningful_action=None,
    ) | {"rebuilt": True, "rows_used": len(rows)}