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