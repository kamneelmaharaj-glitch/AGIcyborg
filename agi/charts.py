# agi/charts.py
from __future__ import annotations
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta

def _fetch_energy(sb, days: int = 45) -> pd.DataFrame:
    start = (datetime.utcnow() - timedelta(days=days)).isoformat()
    cols = "created_at, energy_score, presence_score, theme, mood, tags"
    try:
        res = (
            sb.table("user_reflections")
              .select(cols)
              .gte("created_at", start)
              .order("created_at", desc=False)
              .execute()
        )
        return pd.DataFrame(res.data or [])
    except Exception as e:
        st.info(f"Energy view unavailable: {e}")
        return pd.DataFrame()

def render_energy_section(sb, days: int = 45):
    st.markdown("---")
    st.subheader("🌡️ Ambient Energy")
    df = _fetch_energy(sb, days)
    if df.empty or ("energy_score" not in df.columns):
        st.caption("Not enough data yet. Your energy signal will wake up as you add reflections.")
        return

    # timestamps
    if "created_at" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["created_at"]):
        try:
            df["created_at"] = pd.to_datetime(df["created_at"], format="ISO8601", utc=True, errors="coerce")
        except TypeError:
            df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    if "created_at" in df.columns and pd.api.types.is_datetime64_any_dtype(df["created_at"]):
        if df["created_at"].dt.tz is None:
            df["created_at"] = df["created_at"].dt.tz_localize("UTC")
    df = df.dropna(subset=["created_at"])

    # features
    df["date"] = df["created_at"].dt.date
    df["hour"] = pd.to_numeric(df["created_at"].dt.hour, errors="coerce").astype("Int64").clip(0, 23)
    df["wday"] = df["created_at"].dt.day_name()
    WEEKDAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    df["wday"] = pd.Categorical(df["wday"], categories=WEEKDAYS, ordered=True)

    df["energy_score"] = pd.to_numeric(df["energy_score"], errors="coerce")
    if "presence_score" in df.columns:
        df["presence_score"] = pd.to_numeric(df["presence_score"], errors="coerce")

    # 1) Daily trend
    if "presence_score" in df.columns:
        daily = (
            df.groupby("date", as_index=False)
              .agg(energy=("energy_score","mean"),
                   presence=("presence_score","mean"))
              .sort_values("date")
        )
        y_cols = ["energy","presence"]
    else:
        daily = (
            df.groupby("date", as_index=False)
              .agg(energy=("energy_score","mean"))
              .sort_values("date")
        )
        y_cols = ["energy"]

    if not daily.empty:
        if "energy" in daily.columns:
            daily["energy_smooth"] = daily["energy"].rolling(3, min_periods=1).mean()
        base = alt.Chart(daily).encode(x=alt.X("date:T", title="Date"))
        layers = []
        if "energy_smooth" in daily.columns:
            layers.append(base.mark_line().encode(y=alt.Y("energy_smooth:Q", title="Energy (−1..+1)")))
        if "energy" in daily.columns:
            layers.append(base.mark_point(size=30, opacity=0.65).encode(y="energy:Q", tooltip=y_cols + ["date"]))
        if "presence" in daily.columns:
            layers.append(base.mark_line(strokeDash=[4,3], opacity=.8).encode(y=alt.Y("presence:Q", title="Presence (−1..+1)")))
        st.altair_chart(alt.layer(*layers).properties(height=220), use_container_width=True)
    else:
        st.caption("No daily data yet.")

    # 2) Week heatmap
    heat = df[["wday","hour","energy_score"]].dropna()
    if not heat.empty:
        bucket = (
            heat.groupby(["wday","hour"], as_index=False)
                .agg(energy=("energy_score","mean"))
        )
        cmap = alt.Scale(domain=[-1, 0, 1], range=["#ff7a7a", "#2e3440", "#7ee787"])
        h = (
            alt.Chart(bucket)
               .mark_rect()
               .encode(
                    x=alt.X("hour:O", title="Hour"),
                    y=alt.Y("wday:O", title="Day"),
                    color=alt.Color("energy:Q", title="Energy", scale=cmap),
                    tooltip=["wday","hour","energy"]
               )
               .properties(height=200)
        )
        st.altair_chart(h, use_container_width=True)
    else:
        st.caption("No hourly/weekday pattern yet.")

    # 3) Tags pulse (top 10)
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
            top.columns = ["tag","count"]
            bar = (
                alt.Chart(top)
                   .mark_bar()
                   .encode(
                       x=alt.X("count:Q", title="Count"),
                       y=alt.Y("tag:N", sort="-x", title=None),
                       tooltip=["tag","count"]
                   )
                   .properties(height=220, title="Top tags (last 45 days)")
            )
            st.altair_chart(bar, use_container_width=True)

    # Presence mini-indicator
    if "presence_score" in df.columns and df["presence_score"].notna().any():
        last_p = float(df["presence_score"].tail(5).mean())
        st.caption(f"🧭 Presence (recent avg): **{last_p:.2f}**")