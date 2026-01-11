# agi/charts.py
from __future__ import annotations

import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
from typing import Optional


# ---------------------------------------------------------
# Data access
# ---------------------------------------------------------


@st.cache_data(ttl=60)
def _fetch_energy(
    _sb,
    days: int = 45,
    user_id: Optional[str] = None,
    theme: Optional[str] = None,
) -> pd.DataFrame:
    """
    Fetch energy / presence data for the given user + time window.

    This helper is intentionally focused: it just returns a DataFrame with
    the columns needed for the charts. All layout / rendering is handled
    in render_energy_section().
    """
    start = (datetime.utcnow() - timedelta(days=days)).isoformat()

    cols = "created_at, energy_score, presence_score, theme, mood, tags, user_id"
    q = (
        _sb.table("user_reflections")
        .select(cols)
        .gte("created_at", start)
        .order("created_at", desc=False)
    )

    if user_id:
        q = q.eq("user_id", user_id)
    if theme:
        q = q.eq("theme", theme)

    res = q.execute()
    return pd.DataFrame(res.data or [])


# ---------------------------------------------------------
# Main public renderer
# ---------------------------------------------------------


def render_energy_section(sb, days: int = 45, theme: Optional[str] = None) -> None:
    """
    Render the Energy & Presence trend block.

    Design goals:
    - No "recent reflections" cards here (those live in agi.history).
    - One main line chart: smoothed energy + raw points, optional presence line.
    - Short caption that matches the current filter scope (days + theme).
    - Graceful behaviour when there is not enough data.
    """
    from agi.auth import S_USER_ID

    uid = st.session_state.get(S_USER_ID)
    if not uid:
        return

    df = _fetch_energy(sb, days, uid, theme)

    # ---------- Guard: no data ----------
    st.subheader("Energy & Presence trend")

    if df.empty or "energy_score" not in df.columns:
        st.caption(
            "Not enough data yet. Your energy signal will wake up as you add reflections."
        )
        return

    # ---------- Parse timestamps ----------
    df["created_at"] = pd.to_datetime(
        df.get("created_at"), utc=True, errors="coerce"
    )
    df = df.dropna(subset=["created_at"])
    if df.empty:
        st.caption(
            "Not enough data yet. Your energy signal will wake up as you add reflections."
        )
        return

    # Convenience date column
    df["date"] = df["created_at"].dt.date

    # ---------- Numeric coercion ----------
    df["energy_score"] = pd.to_numeric(df["energy_score"], errors="coerce")

    has_presence = "presence_score" in df.columns
    if has_presence:
        df["presence_score"] = pd.to_numeric(
            df["presence_score"], errors="coerce"
        )

    # ---------- Daily aggregates ----------
    d_energy = (
        df.groupby("date")["energy_score"]
        .mean()
        .reset_index(name="energy")
        .sort_values("date")
    )

    if has_presence:
        d_presence = (
            df.groupby("date")["presence_score"]
            .mean()
            .reset_index(name="presence")
        )
        daily = (
            pd.merge(d_energy, d_presence, on="date", how="outer")
            .sort_values("date")
            .reset_index(drop=True)
        )
    else:
        daily = d_energy

    if daily.empty:
        st.caption("No daily data yet.")
        return

    # ---------- Smoothing ----------
    # Small rolling window so the line doesn’t look jagged but still responds
    # to changes when the user is reflecting more frequently.
    win = int(min(5, max(2, len(daily) // 2)))
    daily["energy_smooth"] = (
        daily["energy"].rolling(win, min_periods=1).mean()
    )

    # ---------- Chart caption ----------
    scope_label = theme if theme else "All themes"
    st.caption(f"Last {days} days • scope: {scope_label}")

    # ---------- Altair chart ----------
    base = alt.Chart(daily).encode(
        x=alt.X("date:T", title="Date"),
    )

    tooltip_cols = ["date", "energy"]
    if has_presence:
        tooltip_cols.append("presence")

    layers = [
        # Smoothed energy line
        base.mark_line().encode(
            y=alt.Y("energy_smooth:Q", title="Energy / Presence"),
        ),
        # Raw energy points
        base.mark_point(size=30, opacity=0.75).encode(
            y="energy:Q",
            tooltip=tooltip_cols,
        ),
    ]

    if has_presence:
        # Optional dashed presence line
        layers.append(
            base.mark_line(strokeDash=[4, 3], opacity=0.85).encode(
                y=alt.Y("presence:Q", title="Presence"),
            )
        )

    chart = alt.layer(*layers).properties(height=220)
    st.altair_chart(chart, use_container_width=True)

    # ---------- Small numeric hint (recent presence) ----------
    if has_presence and df["presence_score"].notna().any():
        last_p = float(df["presence_score"].tail(5).mean())
        st.caption(f"🧭 Recent presence (last few entries): **{last_p:.2f}**")