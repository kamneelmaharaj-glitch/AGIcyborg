# agi/metrics.py
from __future__ import annotations
import streamlit as st
import pandas as pd
import altair as alt
from datetime import timedelta
from typing import Optional, Tuple, List
from html import escape
import textwrap

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


def _energy_to_tint_rgb(energy_norm: float) -> str:
    """
    Map normalized energy (0..1) to a tint RGB for --b.
    0.0 -> cool teal, 0.5 -> green, 1.0 -> warm gold.
    """
    e = max(0.0, min(1.0, float(energy_norm)))
    if e < 0.5:
        t = e / 0.5
        r = int(64 + (64 - 64) * t)        # 64 -> 64
        g = int(200 + (255 - 200) * t)     # 200 -> 255
        b = int(255 + (160 - 255) * t)     # 255 -> 160
    else:
        t = (e - 0.5) / 0.5
        r = int(64 + (255 - 64) * t)       # 64 -> 255
        g = int(255 + (215 - 255) * t)     # 255 -> 215
        b = int(160 + (120 - 160) * t)     # 160 -> 120
    return f"{r},{g},{b}"


# ---------- data fetch (cache by user, not client) ----------
@st.cache_data(ttl=60)
def _fetch_user_data(_sb, user_id: str, days: int = 90) -> Tuple[pd.DataFrame, pd.DataFrame]:
    since = (pd.Timestamp.now(tz="UTC") - timedelta(days=days)).isoformat()

    r1 = (
        _sb.table("user_reflections")
          .select("created_at, theme, energy_score, presence_score, mood, tags, user_id, reflection_text")
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
    - Uses reflection rows for energy_score (and presence_score if available).
    - Falls back to presence sessions for presence if reflections lack it.
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
               .groupby("date", as_index=False)["energy_score"].mean()
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
               .groupby("date", as_index=False)["presence_score"].mean()
               .rename(columns={"presence_score": "presence"})
        )
    elif not df_p.empty and "presence_score" in df_p.columns:
        presence_daily = (
            df_p.dropna(subset=["presence_score"])
               .groupby("date", as_index=False)["presence_score"].mean()
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

    # Smooth window tuned for range
    window = 7 if days <= 30 else 14
    for col, smooth_col in [("energy", "energy_smooth"), ("presence", "presence_smooth")]:
        if col in daily.columns:
            daily[smooth_col] = (
                pd.to_numeric(daily[col], errors="coerce")
                  .rolling(window, min_periods=1)
                  .mean()
            )
    return daily


# --- Dynamic pulse CSS (one-time) -------------------------------------------
def _ensure_pulse_css():
    """Inject CSS once. v1.1: slower breathe, micro-fade text, light/dark adaptive glow, energy orb."""
    if st.session_state.get("_pulse_css_loaded"):
        return

    st.markdown(
        """
<style>
/* Pulse card (theme aura via --a, energy tint via --b) */
.pulse-card {
  --a: 64,255,160;       /* theme aura RGB (primary) */
  --b: 64,255,160;       /* energy tint RGB (secondary, varies with energy) */
  --period: 8.5s;        /* breathing period */
  position: relative;
  padding: 14px 18px;
  border-radius: 12px;
  border: 1px solid rgba(var(--a), 0.30);
  background:
    radial-gradient(120% 120% at 10% 0%, rgba(var(--a), 0.16), rgba(40,44,52,0.40) 60%),
    radial-gradient(60% 100% at 100% 100%, rgba(var(--b), 0.10), transparent 60%),
    rgba(22,26,31,0.35);
  box-shadow: 0 0 0 0 rgba(var(--a), 0.28);
  animation: agiPulse var(--period) ease-in-out infinite;
  will-change: transform, box-shadow;
  overflow: hidden;
}

/* Top highlight */
.pulse-card::before {
  content: "";
  position: absolute;
  inset: -2px;
  border-radius: 12px;
  background: radial-gradient(80% 80% at 15% 0%, rgba(var(--a), 0.22), transparent 60%);
  filter: blur(8px);
  pointer-events: none;
}

/* Ambient shimmer on hover */
.pulse-card::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: 12px;
  background: linear-gradient(120deg,
              transparent 0%,
              rgba(255,255,255,0.08) 45%,
              transparent 60%);
  transform: translateX(-120%);
  opacity: 0;
}
.pulse-card:hover::after {
  animation: shimmer 1.2s ease-out 1;
  opacity: 1;
}

/* One-time glow echo (adds to breathing) */
.pulse-card.pulse-echo {
  animation:
    echo 1.6s ease-out 1,
    agiPulse var(--period) ease-in-out infinite 0.0s;
}

/* Keyframes */
@keyframes agiPulse {
  0%   { box-shadow: 0 0  0px  0px rgba(var(--a), 0.28); transform: scale(1.000); }
  30%  { box-shadow: 0 0 26px 10px rgba(var(--a), 0.22); transform: scale(1.010); }
  55%  { box-shadow: 0 0 34px 14px rgba(var(--a), 0.16); transform: scale(1.005); }
  100% { box-shadow: 0 0  0px  0px rgba(var(--a), 0.28); transform: scale(1.000); }
}
@keyframes echo {
  0%   { box-shadow: 0 0 0 0 rgba(var(--b), 0.35); }
  100% { box-shadow: 0 0 0 24px rgba(var(--b), 0.00); }
}
@keyframes shimmer {
  0%   { transform: translateX(-120%); }
  100% { transform: translateX(120%); }
}

/* Respect user's motion */
@media (prefers-reduced-motion: reduce) {
  .pulse-card, .pulse-card.pulse-echo { animation: none; }
  .pulse-card::after { display: none; }
}

/* Optional inner text styles */
.pc-date   { color: rgba(255,255,255,0.62); font-size: 0.82rem; margin-bottom: 0.25rem; }
.pc-theme  { font-weight: 600; font-size: 1.1rem; margin-bottom: 0.15rem; }
.pc-line   { color: rgba(255,255,255,0.82); font-size: 0.92rem; margin-bottom: 0.35rem; }
.pc-text   { color: rgba(255,255,255,0.88); }
.pc-mentor { color: rgba(155,235,180,0.85); font-size: 0.88rem; font-style: italic; margin-top: 0.45rem; }
</style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state["_pulse_css_loaded"] = True


def _theme_to_aura_rgb(theme: str) -> str:
    """
    Map theme/pillar -> aura RGB string "R,G,B"
    Defaults to Presence green if unknown.
    """
    t = (theme or "").strip().lower()
    palette = {
        "presence": "64,255,160",   # Green
        "clarity":  "160,160,255",  # Soft violet/indigo
        "balance":  "80,200,255",   # Calm blue
        "service":  "255,215,120",  # Golden
        "awareness": "208,160,255",
        "reflection": "100,220,200",
    }
    for key, rgb in palette.items():
        if key in t:
            return rgb
    return palette["presence"]


# ---------- render ----------
def render_user_metrics(sb, user_id: Optional[str], days: int = 30, theme: Optional[str] = None) -> None:
    if not user_id:
        return

    df_r, df_p = _fetch_user_data(sb, user_id, days=days)
    df_r = _ensure_dt(df_r, "created_at")
    if theme and theme != "All" and ("theme" in df_r.columns):
        df_r = df_r[df_r["theme"] == theme]
    df_p = _ensure_dt(df_p, "created_at")

    # --- Reflections counts & streak ---
    total_reflections = len(df_r)
    if "created_at" in df_r.columns and not df_r.empty:
        cutoff_7  = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=7)
        last_7    = df_r[df_r["created_at"] >= cutoff_7]
        reflections_7d = len(last_7)

        dates_desc = sorted(df_r["created_at"].tolist(), reverse=True)
        streak_days = _streak(dates_desc)

        # handle tz-aware/naive safely
        _last = df_r.iloc[0]["created_at"]
        if getattr(_last, "tzinfo", None) is None:
            _last = _last.tz_localize("UTC")
        else:
            _last = _last.tz_convert("UTC")
        last_when = _last.strftime("%b %d, %Y • %H:%M UTC")
    else:
        reflections_7d, streak_days, last_when = 0, 0, "—"

    # --- Top theme ---
    top_theme = (
        df_r["theme"].value_counts().idxmax()
        if ("theme" in df_r.columns and not df_r.empty)
        else "—"
    )

    # --- Presence averages (safe) ---
    avg_presence = float(_safe_series(df_p, "presence_score").astype("float64").mean()) if not df_p.empty else 0.0
    avg_dur      = float(_safe_series(df_p, "duration_sec").astype("float64").mean()) if not df_p.empty else 0.0

    # ---------- Your Week at a Glance ----------
    st.markdown("### 📊 Your Week at a Glance")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Reflections (7d)", reflections_7d)
    c2.metric("Total Reflections", total_reflections)
    c3.metric("Streak (days)", streak_days)
    c4.metric("Avg Presence", f"{avg_presence:.2f}")
    c5.metric("Avg Presence Time", f"{avg_dur:.0f}s")

    st.caption(f"Range: last 30 days — Theme: {top_theme if top_theme!='—' else '—'}")
    st.caption(f"Most active theme: {top_theme}")
    st.caption(f"Last reflection: {last_when}")
    st.markdown("---")

    # ---------- Mirror Mode ----------
    st.markdown("### 🪞 Mirror Mode")
    st.caption("Awareness meets reflection — a gentle view of your recent inner signals.")

    cutoff_30 = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=30)
    df30 = df_r[df_r["created_at"] >= cutoff_30] if "created_at" in df_r.columns else pd.DataFrame()

    if not df30.empty:
        # Mirror stats
        e_series = pd.to_numeric(df30.get("energy_score"), errors="coerce")
        p_series = pd.to_numeric(df30.get("presence_score"), errors="coerce")

        avg_energy_now   = float(e_series.mean(skipna=True)) if not e_series.dropna().empty else 0.0
        avg_presence_now = float(p_series.mean(skipna=True)) if not p_series.dropna().empty else 0.0

        prior_cut   = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=60)
        df_prev     = df_r[(df_r["created_at"] < cutoff_30) & (df_r["created_at"] >= prior_cut)]
        e_prev      = pd.to_numeric(df_prev.get("energy_score"), errors="coerce") if not df_prev.empty else pd.Series(dtype="float64")
        avg_energy_prev = float(e_prev.mean(skipna=True)) if not e_prev.dropna().empty else avg_energy_now

        trend = _trend_name(avg_energy_now, avg_energy_prev)
        entries = len(df30)

        box = st.container(border=True)
        with box:
            cA, cB, cC, cD = st.columns([1, 1, 1, 1])
            cA.metric("Entries", entries)
            cB.metric("Avg Energy", f"{avg_energy_now:.2f}")
            cC.metric("Avg Presence", f"{avg_presence_now:.2f}")
            cD.metric("Top Theme", top_theme if top_theme != "—" else "—")
            st.caption(f"Last reflection: {last_when} • Overall feeling: {trend} • Trend: → {trend}")

            # Orb + note
            orb_col, note_col = st.columns([1, 3])
            with orb_col:
                render_breath_orb(avg_energy_now, avg_presence_now, size=120)
            with note_col:
                st.write(
                    f"Your field feels **{trend}** on average. Presence practices are averaging "
                    f"**{avg_presence_now:.2f}**, keep noticing the **breathe–soften–receive** cycle."
                )

        # --- Latest reflection pulse card ---
        last_row = df30.sort_values("created_at", ascending=False).iloc[0]
        created = last_row.get("created_at")
        created_str = (
            created.tz_convert("UTC").strftime("%b %d, %Y • %H:%M UTC")
            if pd.notna(created) else "—"
        )
        theme_val = last_row.get("theme", "—")
        e_val     = last_row.get("energy_score", None)
        p_val     = last_row.get("presence_score", None)
        text      = last_row.get("reflection_text", "")

        # CSS + colors
        _ensure_pulse_css()
        aura_rgb = _theme_to_aura_rgb(str(theme_val))

        # Normalize energy to 0..1 and compute tint/period
        try:
            energy_norm = max(-1.0, min(1.0, float(e_val)))
            energy_norm = (energy_norm + 1.0) / 2.0
        except Exception:
            energy_norm = 0.5
        tint_rgb = _energy_to_tint_rgb(energy_norm)
        period   = 8.5 - (energy_norm * 2.0)  # ~8.5 .. 6.5
        echo_cls = " pulse-echo" if st.session_state.get("just_saved") else ""

        # Safe content
        safe_text    = escape(text or "")
        metrics_line = f"Energy: {e_val if e_val is not None else '—'} • Presence: {p_val if p_val is not None else '—'}"
        pc_text_block = f'<div class="pc-text">{safe_text}</div>' if safe_text.strip() else ''

        pulse_html = textwrap.dedent(f"""
            <div class="pulse-card{echo_cls}" style="--a:{aura_rgb}; --b:{tint_rgb}; --period:{period:.1f}s;">
              <div class="pc-date">{escape(created_str)}</div>
              <div class="pc-theme">{escape(theme_val)}</div>
              <div class="pc-line">{escape(metrics_line)}</div>
              {pc_text_block}
              <div class="pc-mentor">Mentor: Take a moment to notice your breath and soften your gaze before responding.</div>
            </div>
        """)
        st.markdown(pulse_html, unsafe_allow_html=True)

        # Reset echo flag so it doesn't repeat on the next rerun
        if st.session_state.get("just_saved"):
            st.session_state["just_saved"] = False

        # Persist for other views if needed
        st.session_state["mirror_avg_energy"]   = avg_energy_now
        st.session_state["mirror_avg_presence"] = avg_presence_now
        st.session_state["mirror_trend"]        = trend

        # --- Trend mini-chart ---
        trend_df = _daily_trend(df_r, df_p, days=days)
        if not trend_df.empty:
            st.caption("Trend over time")
            base = alt.Chart(trend_df).encode(x=alt.X("date:T", title="Date"))

            layers = []
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

            st.altair_chart(alt.layer(*layers).properties(height=220), use_container_width=True)
        else:
            st.caption("Not enough data yet to show a trend.")

        # --- Recent reflections ---
        st.markdown("### Recent reflections")
        for _, row in df30.sort_values("created_at", ascending=False).head(5).iterrows():
            created = row.get("created_at")
            theme_row = row.get("theme", "—")
            e_v = row.get("energy_score", None)
            p_v = row.get("presence_score", None)
            text_row = row.get("reflection_text", "") if "reflection_text" in row else ""
            created_row_str = created.tz_convert("UTC").strftime("%b %d, %Y • %H:%M UTC") if pd.notna(created) else "—"

            item = st.container(border=True)
            with item:
                st.caption(created_row_str)
                st.subheader(theme_row)
                st.caption(f"Energy: {e_v if e_v is not None else '—'} • Presence: {p_v if p_v is not None else '—'}")
                if text_row:
                    st.write(text_row)
                st.caption("Mentor: Take a moment to notice breath and soften your gaze before responding.")
    else:
        st.info("No reflections in the last 30 days yet — your Mirror will awaken as you add entries.")