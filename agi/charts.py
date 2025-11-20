# agi/charts.py
from __future__ import annotations

import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
from typing import Optional

@st.cache_data(ttl=60)
def _fetch_energy(_sb, days: int = 45, user_id: Optional[str] = None, theme: Optional[str] = None) -> pd.DataFrame:
    start = (datetime.utcnow() - timedelta(days=days)).isoformat()
    cols = "created_at, energy_score, presence_score, theme, mood, tags, user_id"
    q = _sb.table("user_reflections").select(cols).gte("created_at", start)
    if user_id:
        q = q.eq("user_id", user_id)
    if theme:
        q = q.eq("theme", theme)
    q = q.order("created_at", desc=False)
    res = q.execute()
    return pd.DataFrame(res.data or [])

def render_energy_section(sb, days: int = 45, theme: Optional[str] = None):
    from agi.auth import S_USER_ID

    uid = st.session_state.get(S_USER_ID)
    df = _fetch_energy(sb, days, uid, theme)

    if df.empty or "energy_score" not in df.columns:
        st.caption("Not enough data yet. Your energy signal will wake up as you add reflections.")
        return

    # Parse timestamps + derive convenience columns
    df["created_at"] = pd.to_datetime(df.get("created_at"), utc=True, errors="coerce")
    df = df.dropna(subset=["created_at"])
    if df.empty:
        st.caption("Not enough data yet. Your energy signal will wake up as you add reflections.")
        return

    df["date"] = df["created_at"].dt.date
    df["hour"] = pd.to_numeric(df["created_at"].dt.hour, errors="coerce").astype("Int64").clip(0, 23)
    df["wday"] = df["created_at"].dt.day_name()
    WEEKDAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    df["wday"] = pd.Categorical(df["wday"], categories=WEEKDAYS, ordered=True)

    # Coerce numeric
    df["energy_score"] = pd.to_numeric(df["energy_score"], errors="coerce")
    if "presence_score" in df.columns:
        df["presence_score"] = pd.to_numeric(df["presence_score"], errors="coerce")

    # ---------- 1) Daily trend (robust: compute separately then merge) ----------
    d_energy = (
        df.groupby("date")["energy_score"]
          .mean()
          .reset_index(name="energy")
          .sort_values("date")
    )

    if "presence_score" in df.columns:
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

    win = int(min(5, max(2, len(daily)//2)))
    daily["energy_smooth"] = daily["energy"].rolling(win, min_periods=1).mean()

    base = alt.Chart(daily).encode(x=alt.X("date:T", title="Date"))
    tooltip_cols = ["date","energy"] + (["presence"] if "presence" in daily.columns else [])
    layers = [
        base.mark_line().encode(y=alt.Y("energy_smooth:Q", title="Energy / Presence")),
        base.mark_point(size=30, opacity=0.75).encode(y="energy:Q", tooltip=tooltip_cols),
    ]
    if "presence" in daily.columns:
        layers.append(
            base.mark_line(strokeDash=[4,3], opacity=0.8)
                .encode(y=alt.Y("presence:Q", title="Presence"))
        )
    st.altair_chart(alt.layer(*layers).properties(height=220), use_container_width=True)

    # ---------- 2) Week heatmap ----------
    if {"wday", "hour", "energy_score"}.issubset(df.columns):
        heat = df[["wday","hour","energy_score"]].dropna()
        if not heat.empty:
            bucket = (
                heat.groupby(["wday","hour"])["energy_score"]
                    .mean()
                    .reset_index(name="energy")
            )
            cmap = alt.Scale(domain=[-1, 0, 1], range=["#ff7a7a", "#2e3440", "#7ee787"])
            h = (
                alt.Chart(bucket)
                   .mark_rect()
                   .encode(
                       x=alt.X("hour:O", title="Hour"),
                       y=alt.Y("wday:O", title="Day"),
                       color=alt.Color("energy:Q", title="Energy", scale=cmap),
                       tooltip=["wday","hour","energy"],
                   )
                   .properties(height=200)
                   .configure_scale(bandPaddingInner=0.25, bandPaddingOuter=0.15)
            )
            st.altair_chart(h, use_container_width=True)
        else:
            st.caption("No hourly/weekday pattern yet.")
    else:
        st.caption("No hourly/weekday pattern yet.")

    # ---------- 3) Tags pulse ----------
    if "tags" in df.columns and df["tags"].notna().any():
        def _explode(series: pd.Series) -> list:
            out = []
            for v in series.dropna():
                if isinstance(v, list):
                    out.extend(v)
            return out
        tag_list = _explode(df["tags"])
        if tag_list:
            top = pd.Series(tag_list).value_counts().head(10).reset_index()
            top.columns = ["tag", "count"]
            bar = (
                alt.Chart(top)
                   .mark_bar()
                   .encode(
                       x=alt.X("count:Q", title="Count"),
                       y=alt.Y("tag:N", sort="-x", title=None),
                       tooltip=["tag","count"],
                   )
                   .properties(height=220, title=f"Top tags (last {days} days" + (f", theme {theme})" if theme else ")"))
            )
            st.altair_chart(bar, use_container_width=True)

    # ---------- Presence mini-indicator ----------
    if "presence_score" in df.columns and df["presence_score"].notna().any():
        last_p = float(df["presence_score"].tail(5).mean())
        st.caption(f"🧭 Presence (recent avg): **{last_p:.2f}**")