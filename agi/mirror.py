# agi/mirror.py
from __future__ import annotations
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Tuple

# ---------- helpers
def _ensure_dt(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if col not in df.columns or df.empty:
        return df
    df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")
    return df.dropna(subset=[col])

def _fmt_dt(ts: pd.Timestamp) -> str:
    try:
        return ts.tz_convert("UTC").strftime("%b %d, %Y • %H:%M UTC")
    except Exception:
        return "—"

def _energy_word(x: float | None) -> str:
    if x is None: return "—"
    if x >= 0.35: return "uplifted"
    if x >= 0.05: return "steady"
    if x <= -0.35: return "drained"
    if x <= -0.05: return "softened"
    return "neutral"

# ---------- data fetch (cache; underscore client param so Streamlit can hash)
@st.cache_data(ttl=60)
def _fetch_reflections(_sb, user_id: str, days: int = 30, theme: Optional[str] = None) -> pd.DataFrame:
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    cols = "id, created_at, theme, energy_score, presence_score, reflection_text, generated_insight, tags, user_id"
    q = (
        _sb.table("user_reflections")
           .select(cols)
           .gte("created_at", since)
           .eq("user_id", user_id)
    )
    if theme:
        q = q.eq("theme", theme)
    q = q.order("created_at", desc=True)
    res = q.execute()
    df = pd.DataFrame(res.data or [])
    df = _ensure_dt(df, "created_at")
    # coerce numeric (safe)
    for c in ("energy_score", "presence_score"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

# ---------- core computation
def _mirror_summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "n": 0,
            "avg_energy": None,
            "avg_presence": None,
            "top_theme": "—",
            "last_time": "—",
            "delta_energy": None,
        }

    avg_energy   = float(df["energy_score"].mean()) if "energy_score" in df else None
    avg_presence = float(df["presence_score"].mean()) if "presence_score" in df else None
    top_theme    = df["theme"].value_counts().idxmax() if "theme" in df else "—"
    last_time    = _fmt_dt(df.iloc[0]["created_at"]) if "created_at" in df else "—"

    # “trend” = last 3 vs prior 3 mean
    last3  = df.head(3)["energy_score"].dropna() if "energy_score" in df else pd.Series(dtype="float64")
    prev3  = df.iloc[3:6]["energy_score"].dropna() if "energy_score" in df else pd.Series(dtype="float64")
    delta  = (last3.mean() - prev3.mean()) if len(last3) and len(prev3) else None

    return {
        "n": len(df),
        "avg_energy":   avg_energy,
        "avg_presence": avg_presence,
        "top_theme":    top_theme,
        "last_time":    last_time,
        "delta_energy": float(delta) if delta is not None else None,
    }

# ---------- UI
def render_mirror_panel(sb, user_id: str, days: int = 30, theme: Optional[str] = None) -> None:
    """Draw Mirror Mode v1 — summary + 3 tiles + gentle insights."""
    if not user_id:
        return

    df = _fetch_reflections(sb, user_id, days=days, theme=theme)

    st.subheader("🪞 Mirror Mode")
    st.caption("Awareness meets reflection — a gentle view of your recent inner signals.")

    if df.empty:
        st.info("No reflections in this range yet. Once you write a few, your Mirror will awaken.")
        return

    # top summary
    S = _mirror_summary(df)
    e_word = _energy_word(S["avg_energy"])
    delta  = S["delta_energy"]
    delta_txt = "↗︎ improving" if (delta is not None and delta > 0.02) else ("↘︎ softening" if (delta is not None and delta < -0.02) else "→ steady")

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1,1,1,1])
        c1.metric("Entries", S["n"])
        c2.metric("Avg Energy", f"{S['avg_energy']:.2f}" if S["avg_energy"] is not None else "—")
        c3.metric("Avg Presence", f"{S['avg_presence']:.2f}" if S["avg_presence"] is not None else "—")
        c4.metric("Top Theme", S["top_theme"])
        st.caption(f"Last reflection: **{S['last_time']}** • Overall feeling: **{e_word}** • Trend: **{delta_txt}**")

    # three most recent tiles
    tiles = df.head(3).copy()
    if tiles.empty:
        return

    st.markdown("#### Recent reflections")
    cols = st.columns(len(tiles))
    e_min, e_max = -1.0, 1.0

    for i, (_, row) in enumerate(tiles.iterrows()):
        energy = row.get("energy_score", None)
        presence = row.get("presence_score", None)
        theme = row.get("theme", "—")
        when = _fmt_dt(row.get("created_at"))
        text = (row.get("reflection_text") or "").strip()
        insight = (row.get("generated_insight") or "").strip()

        # gentle card
        with cols[i]:
            glow_alpha = 0.2 + 0.5 * max(0.0, float(energy or 0))  # more positive -> warmer glow
            st.markdown(
                f"""
                <div style="
                    padding:14px;border-radius:16px;
                    background: linear-gradient(180deg, rgba(125, 200, 160,{glow_alpha}) 0%, rgba(80, 90, 100,0.08) 100%);
                    border: 1px solid rgba(255,255,255,0.06);
                ">
                  <div style="font-size:12px;opacity:.8">{when}</div>
                  <div style="font-weight:600;margin-top:4px">{theme}</div>
                  <div style="font-size:12px;margin-top:2px;opacity:.9">
                    Energy: {('%.2f' % energy) if energy is not None else '—'} • Presence: {('%.2f' % presence) if presence is not None else '—'}
                  </div>
                  <div style="font-size:13px;margin-top:8px">{text[:200] + ('…' if len(text) > 200 else '')}</div>
                  {"<hr style='opacity:.12;margin:10px 0 8px 0'/>" if insight else ""}
                  {f"<div style='font-size:12px;opacity:.9'><b>Mentor:</b> {insight[:220]}{'…' if len(insight)>220 else ''}</div>" if insight else ""}
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Mirror insight paragraph
    with st.container():
        e = S["avg_energy"]
        p = S["avg_presence"]
        tone = _energy_word(e)
        insight_lines = []
        if tone != "—":
            insight_lines.append(f"Your field feels **{tone}** on average.")
        if p is not None:
            insight_lines.append(f"Presence practices are averaging **{p:.2f}**, keep noticing the breath-soften-receive cycle.")
        if delta is not None:
            if delta > 0.02:
                insight_lines.append("Energy is trending upward — small actions are compounding.")
            elif delta < -0.02:
                insight_lines.append("Energy is softening — slower rhythms and grounding may help.")
            else:
                insight_lines.append("Energy trend is steady — consistency is serving you.")

        if insight_lines:
            st.markdown("> " + " ".join(insight_lines))