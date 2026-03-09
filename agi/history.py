# agi/history.py — clean, filter-aware reflection history

from __future__ import annotations

import streamlit as st
from typing import Optional, List, Dict
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from html import escape

from agi.auth import S_USER_ID


# ---------- time helpers ----------

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _fmt_when(ts: Optional[str]) -> str:
    """
    Format an ISO timestamp string as 'MMM DD, YYYY • HH:MM UTC'.
    Falls back to raw string if parsing fails.
    """
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        return dt.strftime("%b %d, %Y • %H:%M UTC")
    except Exception:
        return ts or "—"


# ---------- DB helper ----------

def _fetch_reflections_window(
    sb,
    user_id: str,
    *,
    days: int,
    theme: Optional[str] = None,
) -> List[Dict]:
    """
    Load recent reflections for this user in the last N days, newest first.

    Returns a list of dicts from user_reflections.
    """
    if not (sb and user_id):
        return []

    since = (_utc_now() - timedelta(days=days)).isoformat()

    try:
        q = (
            sb.table("user_reflections")
              .select(
                  "id, created_at, theme, mood, tags, tags_raw, "
                  "energy_score, presence_score, reflection_text"
              )
              .eq("user_id", user_id)
              .gte("created_at", since)
              .order("created_at", desc=True)
        )
        if theme:
            q = q.eq("theme", theme)

        res = q.execute()
        return res.data or []
    except Exception as e:  # pragma: no cover
        st.caption(f"Reflection history unavailable: {e}")
        return []

def _fetch_presence_memory_window(
    sb,
    user_id: str,
    *,
    limit: int = 7,
) -> List[Dict]:
    """
    Load recent reflection_memory rows for this user, newest first.
    Used for presence continuity visualization.
    """
    if not (sb and user_id):
        return []

    try:
        res = (
            sb.table("reflection_memory")
              .select("created_at, presence_stage, presence_drift_hits_new, mood, theme")
              .eq("user_id", user_id)
              .order("created_at", desc=True)
              .limit(limit)
              .execute()
        )
        return res.data or []
    except Exception as e:  # pragma: no cover
        st.caption(f"Presence continuity unavailable: {e}")
        return []
    
# ---------- UI helpers ----------

def _group_by_date(rows: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Group rows by date string 'YYYY-MM-DD' (UTC).
    Newest dates should still show first after grouping.
    """
    buckets: Dict[str, List[Dict]] = defaultdict(list)

    for r in rows:
        ts = r.get("created_at")
        try:
            dt = datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            day_str = dt.date().isoformat()
        except Exception:
            # If parsing fails, put into a generic bucket
            day_str = "unknown"
        buckets[day_str].append(r)

    return buckets


def _render_reflection_card(row: Dict) -> None:
    """
    Render a single reflection in a simple, safe card.
    No user HTML is rendered as HTML; everything is treated as plain text.
    """
    theme = (row.get("theme") or "Reflection").strip() or "Reflection"
    when = _fmt_when(row.get("created_at"))

    mood = (row.get("mood") or "").strip()
    tags = row.get("tags")
    tags_raw = (row.get("tags_raw") or "").strip()

    energy = row.get("energy_score")
    presence = row.get("presence_score")

    text = row.get("reflection_text") or ""
    text = text.strip()

    with st.container(border=True):
        # Header line: theme + timestamp
        st.markdown(f"**{theme}**")
        st.caption(when)

        # Mood / tags row (compact, only if present)
        info_bits = []
        if mood:
            info_bits.append(f"mood: _{escape(mood)}_")
        # Prefer structured tags if they exist
        tag_list: List[str] = []
        if isinstance(tags, list):
            tag_list.extend([t for t in tags if isinstance(t, str)])
        if tags_raw:
            tag_list.extend([t.strip() for t in tags_raw.split(",") if t.strip()])

        if tag_list:
            tag_str = ", ".join(f"`{escape(t)}`" for t in tag_list)
            info_bits.append(f"tags: {tag_str}")

        if info_bits:
            st.caption(" • ".join(info_bits))

        # Energy / presence row
        if energy is not None or presence is not None:
            metrics_bits = []
            if energy is not None:
                try:
                    metrics_bits.append(f"energy: {float(energy):.1f}")
                except Exception:
                    pass
            if presence is not None:
                try:
                    metrics_bits.append(f"presence: {float(presence):.2f}")
                except Exception:
                    pass
            if metrics_bits:
                st.caption(" / ".join(metrics_bits))

        # Body
        if text:
            # Split into paragraphs and render as plain text (no HTML)
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for p in paragraphs:
                st.write(p)
        else:
            st.caption("_(No reflection text saved.)_")

def _presence_stage_label(stage: Optional[int]) -> str:
    try:
        s = int(stage)
    except Exception:
        return "—"

    mapping = {
        0: "Fragmented",
        1: "Low",
        2: "Steady",
        3: "Strong",
    }
    return mapping.get(s, str(s))


def _presence_stage_bar(stage: Optional[int]) -> str:
    """
    Tiny text bar for stage 0–3.
    """
    try:
        s = max(0, min(3, int(stage)))
    except Exception:
        s = 0
    return "●" * (s + 1) + "○" * (3 - s)


def render_presence_continuity(
    sb,
    *,
    limit: int = 7,
) -> None:
    """
    Gentle recent presence visualization from reflection_memory.
    Shows the latest N reflection events, oldest → newest.
    """
    user_id = st.session_state.get(S_USER_ID)
    if not user_id:
        return

    rows = _fetch_presence_memory_window(sb, user_id, limit=limit)
    if not rows:
        return

    rows = list(reversed(rows))  # oldest -> newest for readable continuity

    st.markdown("### 🌿 Presence continuity")
    st.caption("A gentle view of your recent presence rhythm.")

    for row in rows:
        when = _fmt_when(row.get("created_at"))
        stage = row.get("presence_stage")
        drift_new = row.get("presence_drift_hits_new", 0)

        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            st.caption(when)
        with c2:
            st.caption(f"{_presence_stage_bar(stage)}  {_presence_stage_label(stage)}")
        with c3:
            try:
                drift_val = int(drift_new or 0)
            except Exception:
                drift_val = 0
            if drift_val > 0:
                st.caption(f"drift +{drift_val}")
            else:
                st.caption("")

    st.markdown("---")
    
# ---------- Public API ----------

def render_recent_reflections(
    sb,
    *,
    days: int = 30,
    theme: Optional[str] = None,
) -> None:
    """
    Main entry point used by app.py.

    - Respects the same `days` and `theme` filters as metrics.
    - Groups reflections by date (newest → oldest).
    - Uses minimal, clean layout with no HTML leakage.
    """
    user_id = st.session_state.get(S_USER_ID)
    if not user_id:
        return

    rows = _fetch_reflections_window(sb, user_id, days=days, theme=theme)

    scope_label = theme or "All themes"
    st.markdown("### 🧾 Recent reflections")
    st.caption(f"Window: last {days} days • Theme filter: {scope_label}")

    if not rows:
        st.info("No reflections in this window yet. New entries will appear here as you write.")
        return

    # Group by date and render newest dates first
    buckets = _group_by_date(rows)

    # Sort keys (dates) descending; 'unknown' (if any) goes last
    date_keys = sorted(
        [k for k in buckets.keys() if k != "unknown"],
        reverse=True,
    )
    if "unknown" in buckets:
        date_keys.append("unknown")

    for day in date_keys:
        group = buckets[day]
        # Pretty date label
        if day == "unknown":
            label = "Date unknown"
        else:
            try:
                dt = datetime.fromisoformat(day)
                label = dt.strftime("%A, %b %d, %Y")
            except Exception:
                label = day

        st.markdown(f"#### {label}")

        for row in group:
            _render_reflection_card(row)

        st.markdown("---")