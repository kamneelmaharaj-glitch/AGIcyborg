# agi/persistence/snapshots.py
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, List
from collections import Counter


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _week_start_utc(d: datetime) -> str:
    """
    Monday-based week start in UTC, returned as YYYY-MM-DD string.
    """
    dt = d.astimezone(timezone.utc)
    monday = dt.date() - timedelta(days=dt.weekday())  # Monday=0
    return monday.isoformat()


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None or isinstance(v, bool):
            return default
        return int(v)
    except Exception:
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or isinstance(v, bool):
            return default
        return float(v)
    except Exception:
        return default


def fetch_reflections_for_week(
    supabase,
    *,
    user_id: str,
    week_start: str,  # YYYY-MM-DD
    table: str = "reflection_memory",
) -> List[Dict[str, Any]]:
    """
    Reads minimal fields for a given week from reflection_memory (or your source table).
    Adjust `table` if needed.
    Expected columns (best case):
      - created_at (timestamptz)
      - mood (text)
      - silenced (bool)
      - presence_stage (int)
      - presence_drift_hits (int) OR you can infer drift days differently
    """
    if not (supabase and user_id and week_start):
        return []

    # week_end = week_start + 7 days
    from datetime import datetime, timedelta, timezone
    ws_date = datetime.fromisoformat(week_start).date()
    ws_dt = datetime(ws_date.year, ws_date.month, ws_date.day, tzinfo=timezone.utc)
    we_dt = ws_dt + timedelta(days=7)

    try:
        res = (
            sb.table("user_reflections")
            .select("created_at,mood,silenced,presence_stage")  # whatever you need
            .eq("user_id", user_id)
            .gte("created_at", ws_dt.isoformat())
            .lt("created_at", we_dt.isoformat())
            .execute()
        )
        return getattr(res, "data", None) or []
    except Exception:
        return []


def compute_weekly_snapshot(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Deterministic aggregation. No AI.
    """
    if not rows:
        return {
            "reflection_count": 0,
            "avg_presence": 0.0,
            "min_presence": 0,
            "max_presence": 0,
            "drift_days": 0,
            "silence_days": 0,
            "dominant_mood": None,
        }

    presence_vals: List[int] = []
    moods: List[str] = []
    silence_days = 0
    drift_days = 0

    for r in rows:
        ps = _safe_int(r.get("presence_stage"), 0)
        presence_vals.append(ps)

        m = (r.get("mood") or "").strip()
        if m:
            moods.append(m)

        if bool(r.get("silenced")):
            silence_days += 1

        # “drift day” heuristic: presence_drift_hits > 0 on that record
        # If you don’t store presence_drift_hits per reflection_memory, we can change this later.
        if _safe_int(r.get("presence_drift_hits"), 0) > 0:
            drift_days += 1

    avg_presence = sum(presence_vals) / max(len(presence_vals), 1)
    min_presence = min(presence_vals) if presence_vals else 0
    max_presence = max(presence_vals) if presence_vals else 0

    dominant_mood = None
    if moods:
        dominant_mood = Counter(moods).most_common(1)[0][0]

    return {
        "reflection_count": len(rows),
        "avg_presence": round(avg_presence, 2),
        "min_presence": min_presence,
        "max_presence": max_presence,
        "drift_days": drift_days,
        "silence_days": silence_days,
        "dominant_mood": dominant_mood,
    }


def upsert_presence_snapshot(
    supabase,
    *,
    user_id: str,
    week_start: str,
    snapshot: Dict[str, Any],
) -> Dict[str, Any]:
    if not (supabase and user_id and week_start):
        return {"written": False, "reason": "missing_supabase_or_user_or_week"}

    now = _utcnow().isoformat()

    payload = {
        "user_id": str(user_id),
        "week_start": week_start,
        "reflection_count": _safe_int(snapshot.get("reflection_count"), 0),
        "avg_presence": _safe_float(snapshot.get("avg_presence"), 0.0),
        "min_presence": _safe_int(snapshot.get("min_presence"), 0),
        "max_presence": _safe_int(snapshot.get("max_presence"), 0),
        "drift_days": _safe_int(snapshot.get("drift_days"), 0),
        "silence_days": _safe_int(snapshot.get("silence_days"), 0),
        "dominant_mood": snapshot.get("dominant_mood"),
        "updated_at": now,
    }

    try:
        res = (
            supabase.table("presence_snapshots")
            .upsert(payload, on_conflict="user_id,week_start")
            .execute()
        )
        return {"written": True, "payload": payload, "data": getattr(res, "data", None)}
    except Exception as e:
        return {"written": False, "payload": payload, "error": str(e)[:200]}


def refresh_weekly_presence_snapshot(
    supabase,
    *,
    user_id: str,
    at: Optional[datetime] = None,
    source_table: str = "reflection_memory",
) -> Dict[str, Any]:
    """
    End-to-end: fetch week rows -> compute -> upsert.
    """
    at = at or _utcnow()
    week_start = _week_start_utc(at)

    rows = fetch_reflections_for_week(
        supabase,
        user_id=str(user_id),
        week_start=week_start,
        table=source_table,
    )
    snap = compute_weekly_snapshot(rows)
    write = upsert_presence_snapshot(
        supabase,
        user_id=str(user_id),
        week_start=week_start,
        snapshot=snap,
    )
    return {"week_start": week_start, "snapshot": snap, "write": write}