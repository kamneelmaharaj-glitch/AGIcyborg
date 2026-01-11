# agi/metrics.py
from __future__ import annotations

import streamlit as st
import pandas as pd
import altair as alt
from datetime import timedelta
from typing import Optional, Tuple, List
from html import escape

from agi.orb import render_breath_orb


# ---------- helpers ----------
def _ensure_dt(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if df.empty or col not in df.columns:
        return df
    df = df.copy()
    df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")
    return df.dropna(subset=[col])


def _safe_series(df: pd.DataFrame, col: str) -> pd.Series:
    return df[col] if col in df.columns else pd.Series(dtype="object")


def _streak(dates_utc: List[pd.Timestamp]) -> int:
    if not dates_utc:
        return 0
    today = pd.Timestamp.now(tz="UTC").normalize()
    seen = {dt.normalize() for dt in dates_utc}
    s, d = 0, today
    while d in seen:
        s += 1
        d = d - pd.Timedelta(days=1)
    return s


def _trend_name(avg_energy_now: float, avg_energy_prior: float) -> str:
    diff = avg_energy_now - avg_energy_prior
    if diff > 0.05:
        return "improving"
    if diff < -0.05:
        return "softening"
    return "steady"


# ---------- data fetch (cache by user, not client) ----------
@st.cache_data(ttl=60)
def _fetch_user_data(
    _sb,
    user_id: str,
    days: int = 90,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    since = (pd.Timestamp.now(tz="UTC") - timedelta(days=days)).isoformat()

    r1 = (
        _sb.table("user_reflections")
        .select(
            "created_at, theme, energy_score, presence_score, mood, tags, "
            "user_id, reflection_text"
        )
        .gte("created_at", since)
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    df_r = pd.DataFrame(r1.data or [])

    r2 = (
        _sb.table("presence_sessions")
        .select("created_at, duration_sec, presence_score, user_id")
        .gte("created_at", since)
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    df_p = pd.DataFrame(r2.data or [])
    return df_r, df_p


# ---------- “Trend Over Time” mini-chart data ----------
def _daily_trend(df_r: pd.DataFrame, df_p: pd.DataFrame, *, days: int) -> pd.DataFrame:
    """
    Returns a dataframe with columns:
      date, energy (mean), presence (mean), energy_smooth, presence_smooth
    """
    if df_r.empty and df_p.empty:
        return pd.DataFrame()

    if not df_r.empty and "created_at" in df_r.columns:
        df_r = df_r.copy()
        df_r["date"] = df_r["created_at"].dt.date
    if not df_p.empty and "created_at" in df_p.columns:
        df_p = df_p.copy()
        df_p["date"] = df_p["created_at"].dt.date

    energy_daily = pd.DataFrame()
    if not df_r.empty and "energy_score" in df_r.columns:
        energy_daily = (
            df_r.dropna(subset=["energy_score"])
            .groupby("date", as_index=False)["energy_score"]
            .mean()
            .rename(columns={"energy_score": "energy"})
        )

    presence_daily = pd.DataFrame()
    if (
        not df_r.empty
        and "presence_score" in df_r.columns
        and df_r["presence_score"].notna().any()
    ):
        presence_daily = (
            df_r.dropna(subset=["presence_score"])
            .groupby("date", as_index=False)["presence_score"]
            .mean()
            .rename(columns={"presence_score": "presence"})
        )
    elif not df_p.empty and "presence_score" in df_p.columns:
        presence_daily = (
            df_p.dropna(subset=["presence_score"])
            .groupby("date", as_index=False)["presence_score"]
            .mean()
            .rename(columns={"presence_score": "presence"})
        )

    if energy_daily.empty and presence_daily.empty:
        return pd.DataFrame()

    if energy_daily.empty:
        daily = presence_daily
        daily["energy"] = pd.NA
    elif presence_daily.empty:
        daily = energy_daily
        daily["presence"] = pd.NA
    else:
        daily = pd.merge(energy_daily, presence_daily, on="date", how="outer")

    daily = daily.sort_values("date").reset_index(drop=True)

    window = 7 if days <= 30 else 14
    for col, smooth_col in [("energy", "energy_smooth"), ("presence", "presence_smooth")]:
        if col in daily.columns:
            daily[smooth_col] = (
                pd.to_numeric(daily[col], errors="coerce")
                .rolling(window, min_periods=1)
                .mean()
            )
    return daily

# Render User Metrics
def render_user_metrics(
    sb,
    user_id: Optional[str],
    days: int = 30,
    theme: Optional[str] = None,
) -> None:
    """
    Top-of-page metrics + Mirror summary + latest reflection card + trend mini-chart.

    All metrics respect:
      - days: lookback window in days (for reflections + presence)
      - theme: filter on reflection theme (presence is global)
    """
    if not user_id:
        return

    # 1) Fetch + basic filtering
    df_r, df_p = _fetch_user_data(sb, user_id, days=days)
    df_r = _ensure_dt(df_r, "created_at")
    df_p = _ensure_dt(df_p, "created_at")

    # Theme filter applies only to reflections
    if theme and theme != "All" and ("theme" in df_r.columns):
        df_r = df_r[df_r["theme"] == theme]

    # ---------- Reflections counts & streak ----------
    total_reflections = len(df_r)

    if "created_at" in df_r.columns and not df_r.empty:
        now_utc = pd.Timestamp.now(tz="UTC")
        cutoff_7 = now_utc - pd.Timedelta(days=7)
        last_7 = df_r[df_r["created_at"] >= cutoff_7]
        reflections_7d = len(last_7)

        # streak based on reflection dates
        dates_desc = sorted(df_r["created_at"].tolist(), reverse=True)
        streak_days = _streak(dates_desc)

        _last = df_r.iloc[0]["created_at"]
        if getattr(_last, "tzinfo", None) is None:
            _last = _last.tz_localize("UTC")
        else:
            _last = _last.tz_convert("UTC")
        last_when = _last.strftime("%b %d, %Y • %H:%M UTC")
    else:
        reflections_7d, streak_days, last_when = 0, 0, "—"

    # ---------- Top theme (within current filter) ----------
    top_theme = (
        df_r["theme"].value_counts().idxmax()
        if ("theme" in df_r.columns and not df_r.empty)
        else "—"
    )

    # ---------- Presence averages (global, not themed) ----------
    if not df_p.empty:
        avg_presence = float(
            _safe_series(df_p, "presence_score").astype("float64").mean()
        )
        avg_dur = float(
            _safe_series(df_p, "duration_sec").astype("float64").mean()
        )
    else:
        avg_presence, avg_dur = 0.0, 0.0

    # ---------- Your Week at a Glance ----------
    st.markdown("### 📊 Your Week at a Glance")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Reflections (7d)", reflections_7d)
    c2.metric("Total Reflections", total_reflections)
    c3.metric("Streak (days)", streak_days)
    c4.metric("Avg Presence", f"{avg_presence:.2f}")
    c5.metric("Avg Presence Time", f"{avg_dur:.0f}s")

    st.caption(
        f"Range: last {days} days — "
        f"Theme filter (reflections): {theme or 'All'} • "
        f"Presence is tracked across all themes."
    )
    st.caption(f"Last reflection: {last_when}")
    st.markdown("---")

    # ---------- Mirror Mode summary ----------
    st.markdown("### 🪞 Mirror Mode")
    st.caption("Awareness meets reflection — a gentle view of your recent inner signals.")

    # Use the same days window here, but cap at 30 for smoothing purposes
    window_days = min(days, 30)
    now_utc = pd.Timestamp.now(tz="UTC")
    cutoff_window = now_utc - pd.Timedelta(days=window_days)
    df_window = (
        df_r[df_r["created_at"] >= cutoff_window]
        if "created_at" in df_r.columns
        else pd.DataFrame()
    )

    avg_energy_now = 0.0
    avg_presence_now = 0.0
    trend = "steady"
    entries = len(df_window)

    if not df_window.empty:
        # Basic stats for the current window
        e_series = pd.to_numeric(df_window.get("energy_score"), errors="coerce")
        p_series = pd.to_numeric(df_window.get("presence_score"), errors="coerce")

        avg_energy_now = float(e_series.mean(skipna=True)) if e_series.notna().any() else 0.0
        avg_presence_now = float(p_series.mean(skipna=True)) if p_series.notna().any() else 0.0

        # Compare with immediately preceding window of same length (for trend)
        prior_start = now_utc - pd.Timedelta(days=2 * window_days)
        df_prev = df_r[
            (df_r["created_at"] < cutoff_window)
            & (df_r["created_at"] >= prior_start)
        ]
        if not df_prev.empty:
            e_prev = pd.to_numeric(df_prev.get("energy_score"), errors="coerce")
            avg_energy_prev = float(e_prev.mean(skipna=True)) if e_prev.notna().any() else avg_energy_now
        else:
            avg_energy_prev = avg_energy_now

        trend = _trend_name(avg_energy_now, avg_energy_prev)

    # ----- Mirror summary card (works even if there are 0 entries) -----
    box = st.container(border=True)
    with box:
        cA, cB, cC, cD = st.columns(4)
        cA.metric("Entries", entries)
        cB.metric("Avg Energy", f"{avg_energy_now:.2f}")
        cC.metric("Avg Presence", f"{avg_presence_now:.2f}")
        cD.metric("Top Theme", top_theme if top_theme != "—" else "—")

        if entries > 0:
            st.caption(
                f"Window: last {window_days} days • Overall feeling: {trend} • Trend: → {trend}"
            )

            orb_col, note_col = st.columns([1, 3])
            with orb_col:
                # reuse existing orb helper
                render_breath_orb(avg_energy_now, avg_presence_now, size=120)
            with note_col:
                st.write(
                    f"Your field feels **{trend}** on average. Presence practices are averaging "
                    f"**{avg_presence_now:.2f}**, keep noticing the **breathe–soften–receive** cycle."
                )
        else:
            st.caption(f"Window: last {window_days} days")
            st.write(
                "No reflections in this window yet. Once you log a few reflections, "
                "Mirror Mode will begin to show patterns here."
            )

    # ---------- Latest reflection (simple, text-only card) ----------
    if not df_r.empty and "created_at" in df_r.columns:
        last_row = df_r.sort_values("created_at", ascending=False).iloc[0]

        created = last_row.get("created_at")
        if pd.notna(created):
            created_str = created.tz_convert("UTC").strftime("%b %d, %Y • %H:%M UTC")
        else:
            created_str = "-"

        theme_val = last_row.get("theme", "-") or "-"
        e_val = last_row.get("energy_score", None)
        p_val = last_row.get("presence_score", None)
        raw_text = (last_row.get("reflection_text", "") or "").strip()

        energy_str = "–" if e_val is None else f"{float(e_val):.1f}"
        pres_str   = "–" if p_val is None else f"{float(p_val):.2f}"

        card = st.container(border=True)
        with card:
            st.markdown("#### Latest reflection")
            st.write(f"**{theme_val}**")
            st.caption(f"{created_str} • Energy: {energy_str} • Presence: {pres_str}")

            # Show the first line that looks like the question, if present
            first_line = ""
            body_lines = []
            for line in raw_text.splitlines():
                s = line.strip()
                if not s:
                    continue
                if not first_line and s.lower().startswith("q:"):
                    first_line = s
                else:
                    body_lines.append(line)

            if first_line:
                st.write(f"*{first_line}*")
            if body_lines:
                st.write("\n".join(body_lines))
    else:
        # No reflections at all yet
        card = st.container(border=True)
        with card:
            st.markdown("#### Latest reflection")
            st.caption("No reflections yet. Your first one will appear here.")

    # Persist summary values for other views if needed
    st.session_state["mirror_avg_energy"] = avg_energy_now
    st.session_state["mirror_avg_presence"] = avg_presence_now
    st.session_state["mirror_trend"] = trend

    # ---------- Trend mini-chart ----------
    trend_df = _daily_trend(df_r, df_p, days=days)
    if not trend_df.empty:
        st.caption("Trend over time")
        base = alt.Chart(trend_df).encode(x=alt.X("date:T", title="Date"))

        layers: List[alt.Chart] = []
        if "energy_smooth" in trend_df.columns:
            layers.append(
                base.mark_line().encode(
                    y=alt.Y("energy_smooth:Q", title="Energy (−1…+1)")
                )
            )
            layers.append(
                base.mark_point(size=30, opacity=0.6).encode(
                    y="energy:Q",
                    tooltip=[
                        alt.Tooltip("date:T", title="Date"),
                        alt.Tooltip("energy:Q", format=".2f", title="Energy"),
                    ],
                )
            )
        if "presence_smooth" in trend_df.columns and trend_df["presence_smooth"].notna().any():
            layers.append(
                base.mark_line(strokeDash=[5, 4], opacity=0.9).encode(
                    y=alt.Y("presence_smooth:Q", title="Presence (−1…+1)")
                )
            )

        st.altair_chart(
            alt.layer(*layers).properties(height=220),
            use_container_width=True,
        )
    else:
        st.caption("Not enough data yet to show a trend.")

    # Hint about detailed history
    st.caption("Recent reflections are shown below in the collapsible history section.")