"""
User continuity & lifecycle state.

This module manages long-lived per-user state such as:
- last reflection time
- last meaningful action
- continuity counters
- future memory hooks

This layer is persistence-aware but behavior-driven.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

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
    now = _utcnow()
    reflection_at = reflection_at or now

    # default: treat microstep/action as happening "now" if provided
    if microstep and microstep_at is None:
        microstep_at = now
    if last_meaningful_action and action_at is None:
        action_at = now

    payload: Dict[str, Any] = {
        "user_id": user_id,
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

    # Upsert base row
    res = (
        supabase.table("reflection_state")
        .upsert(payload, on_conflict="user_id")  # important
        .execute()
    )

    # Optional: increment reflection_count via RPC for correctness under concurrency
    # (recommended). If you haven't created the RPC yet, skip this for now.
    if increment_reflection_count:
        try:
            supabase.rpc("increment_reflection_count", {"p_user_id": user_id}).execute()
        except Exception:
            # safe fallback: ignore if RPC not present
            pass

    return {"payload": payload, "upsert": res.data}