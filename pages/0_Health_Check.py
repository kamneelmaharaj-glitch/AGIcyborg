# 0_Health_Check.py
# AGIcyborg.ai — System Health (with refresh, uptime, seeding, and housekeeping)

from __future__ import annotations
import os, time, json, platform
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st
import pandas as pd
from dotenv import load_dotenv

# Optional providers
try:
    from supabase import create_client
except Exception:
    create_client = None

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# -------------------
# Page + constants
# -------------------
st.set_page_config(page_title="AGIcyborg — System Health", page_icon="🩺", layout="wide")

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
PROMPTS_CSV  = DATA_DIR / "reflection_prompts.csv"
INSIGHTS_CSV = DATA_DIR / "mentor_insights.csv"
LOG_CSV      = DATA_DIR / "user_reflections.csv"

STATE_FILE = ROOT / ".health_state.json"  # to persist uptime across reruns
REFRESH_SECS_DEFAULT = 5 * 60


# -------------------
# Utilities
# -------------------
def mask(s: str, head=6, tail=4) -> str:
    if not s:
        return "—"
    s = str(s)
    if len(s) <= head + tail + 3:
        return s
    return f"{s[:head]}…{s[-tail:]}"

def save_state(d: dict) -> None:
    try:
        STATE_FILE.write_text(json.dumps(d, indent=2))
    except Exception:
        pass

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {}
    return {}

@st.cache_resource
def uptime_anchor() -> float:
    """Resource persists for server lifetime; combine with file for cross-rerun uptime."""
    return time.time()

def ensure_uptime_start() -> datetime:
    state = load_state()
    # file-based uptime to persist even when app reruns
    if "started_at" not in state:
        state["started_at"] = datetime.utcnow().isoformat() + "Z"
        save_state(state)
    try:
        return datetime.fromisoformat(state["started_at"].replace("Z",""))
    except Exception:
        # fallback to now
        now = datetime.utcnow()
        state["started_at"] = now.isoformat() + "Z"
        save_state(state)
        return now

def format_delta(td: timedelta) -> str:
    d = td.days
    h, rem = divmod(td.seconds, 3600)
    m, _ = divmod(rem, 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m or not parts: parts.append(f"{m}m")
    return " ".join(parts)

def auto_refresh_meta(every_seconds: int):
    # simple, browser-level refresh
    st.markdown(
        f'<meta http-equiv="refresh" content="{every_seconds}">', unsafe_allow_html=True
    )

def pulse(css_color="#22c55e", visible=True):
    if not visible:
        return
    st.markdown(
        f"""
        <style>
        .pulse {{
          width: 10px; height: 10px; border-radius: 50%;
          background: {css_color}; box-shadow: 0 0 0 rgba(34,197,94, 0.7);
          animation: pulse 2s infinite;
          display:inline-block; margin-left:8px; vertical-align:middle;
        }}
        @keyframes pulse {{
          0% {{ box-shadow: 0 0 0 0 rgba(34,197,94, 0.6); }}
          70% {{ box-shadow: 0 0 0 12px rgba(34,197,94, 0); }}
          100% {{ box-shadow: 0 0 0 0 rgba(34,197,94, 0); }}
        }}
        </style>
        <span class="pulse"></span>
        """,
        unsafe_allow_html=True,
    )


def count_table(table_name: str, csv_path: Path, cols: list[str], sb=None) -> tuple[int, str]:
    """
    Returns (count, message)
    """
    if sb:
        try:
            data = sb.table(table_name).select("*").execute()
            count = len(data.data or [])
            return (count, "ok")
        except Exception as e:
            return (0, f"error: {e}")

    # CSV fallback
    try:
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            # ensure expected cols exist to avoid misleading "ok"
            missing = [c for c in cols if c not in df.columns]
            if missing:
                return (len(df), f"missing cols: {', '.join(missing)}")
            return (len(df), "ok")
        return (0, "not found")
    except Exception as e:
        return (0, f"error: {e}")


# Cache counts for quick reloads (adjust ttl as you like)
# AFTER
@st.cache_data(ttl=30)
def get_counts(_sb):
    prompts_cnt, prompts_msg = count_table(
        "reflection_prompts", PROMPTS_CSV, ["id", "theme", "prompt"], _sb
    )
    insights_cnt, insights_msg = count_table(
        "mentor_insights", INSIGHTS_CSV, ["id", "theme", "insight", "mantra"], _sb
    )
    reflections_cnt, reflections_msg = count_table(
        "user_reflections", LOG_CSV,
        ["prompt_id", "theme", "reflection_text", "generated_insight", "generated_mantra", "created_at"], _sb
    )
    return {
        "prompts":  (prompts_cnt, prompts_msg),
        "insights": (insights_cnt, insights_msg),
        "reflections": (reflections_cnt, reflections_msg),
    }


# -------------------
# Visualization helpers
# -------------------
def render_weight_health(sb, show_title: bool = True):
    """
    Lightweight health panel for frequency_weight. Shows a summary table and guidance.
    """
    if show_title:
        st.header("🧰 Prompt weighting (frequency_weight)")

    # 1) Fetch columns safely
    try:
        res = sb.table("reflection_prompts").select("id, theme, frequency_weight, active").execute() if sb else None
    except Exception as e:
        st.warning(f"Could not read reflection_prompts: {e}")
        return

    df = pd.DataFrame(res.data or []) if res else pd.DataFrame()
    if df.empty:
        st.info("No rows found in `reflection_prompts`.")
        return

    # 2) Column existence check
    if "frequency_weight" not in df.columns:
        st.error("`frequency_weight` column is **missing** in `reflection_prompts`.")
        with st.expander("How to add it (SQL)", expanded=False):
            st.code(
                """\
-- Add the column with a sensible default
alter table public.reflection_prompts
  add column frequency_weight numeric not null default 1;

-- Optional: backfill nulls if column is nullable
update public.reflection_prompts
  set frequency_weight = 1
  where frequency_weight is null;""",
                language="sql",
            )
        return

    # 3) Basic quality checks
    df["frequency_weight"] = pd.to_numeric(df["frequency_weight"], errors="coerce")
    zero_or_null = int((df["frequency_weight"].isna() | (df["frequency_weight"] <= 0)).sum())
    if zero_or_null > 0:
        st.warning(f"{zero_or_null} prompt(s) have **null or non-positive** `frequency_weight` (0/NULL).")

    # 4) Per-theme balance view
    def _bad_count(series):
        s = pd.to_numeric(series, errors="coerce")
        return int((s.fillna(0) <= 0).sum())

    summary = (
        df.groupby("theme", dropna=False)
          .agg(
              prompts=("id", "count"),
              zero_or_null_weight=("frequency_weight", _bad_count),
              mean_weight=("frequency_weight", "mean"),
              min_weight=("frequency_weight", "min"),
              max_weight=("frequency_weight", "max"),
          )
          .reset_index()
          .sort_values(["prompts", "theme"], ascending=[False, True])
    )

    st.dataframe(summary, use_container_width=True)

    with st.expander("Tips to tune weighting"):
        st.markdown(
            """
- Use **larger weights** to surface prompts more often; keep them relative (e.g., 1–5).
- Avoid **0 or NULL** — those make a row effectively unpickable in weighted sampling.
- Keep each theme represented (avoid a theme with all small weights).
            """
        )


def render_weight_charts(sb, show_title: bool = True):
    """
    Draws two bar charts:
      1) Prompt count by theme
      2) Mean frequency_weight by theme
    Uses matplotlib (single plot each, no custom colors).
    """
    if show_title:
        st.header("📊 Prompt distribution & weighting")

    # Safe import of matplotlib
    try:
        import matplotlib.pyplot as plt
    except Exception:
        st.warning(
            "Matplotlib is not installed in this environment. "
            "Install it (`pip install matplotlib`) to see charts."
        )
        return

    # Pull minimal fields
    try:
        res = sb.table("reflection_prompts").select("theme, frequency_weight, active").execute() if sb else None
    except Exception as e:
        st.warning(f"Could not read reflection_prompts: {e}")
        return

    df = pd.DataFrame((res.data or [])) if res else pd.DataFrame()
    if df.empty:
        st.info("No rows found in `reflection_prompts`.")
        return

    # Ensure expected cols
    if "theme" not in df.columns:
        st.error("`theme` column missing.")
        return
    if "frequency_weight" not in df.columns:
        st.error("`frequency_weight` column missing.")
        return

    # Active-only (if column exists)
    if "active" in df.columns:
        df = df[df["active"].fillna(True)]

    # Clean + aggregate
    df["theme"] = df["theme"].astype(str).str.strip()
    df["frequency_weight"] = pd.to_numeric(df["frequency_weight"], errors="coerce").fillna(1)

    counts = (
        df.groupby("theme", dropna=False)["theme"].count()
          .sort_values(ascending=False)
    )

    means = (
        df.groupby("theme", dropna=False)["frequency_weight"].mean()
          .sort_values(ascending=False)
          .round(2)
    )

    # --- Chart 1: count by theme
    fig1, ax1 = plt.subplots()
    counts.plot(kind="bar", ax=ax1)
    ax1.set_title("Prompts per Theme")
    ax1.set_xlabel("Theme")
    ax1.set_ylabel("Count")
    ax1.tick_params(axis="x", labelrotation=45)
    for lbl in ax1.get_xticklabels():
        lbl.set_horizontalalignment("right")
    plt.tight_layout()
    st.pyplot(fig1, use_container_width=True)

    # --- Chart 2: mean weight by theme
    fig2, ax2 = plt.subplots()
    means.plot(kind="bar", ax=ax2)
    ax2.set_title("Mean frequency_weight per Theme")
    ax2.set_xlabel("Theme")
    ax2.set_ylabel("Mean weight")
    ax2.tick_params(axis="x", labelrotation=45)
    for lbl in ax2.get_xticklabels():
        lbl.set_horizontalalignment("right")
    plt.tight_layout()
    st.pyplot(fig2, use_container_width=True)

    st.caption("Tip: Use higher `frequency_weight` for themes you want to surface more often.")


# -------------------
# Environment + clients
# -------------------
load_dotenv(ROOT / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

sb = None
if SUPABASE_URL and SUPABASE_KEY and create_client:
    try:
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        sb = None

oa = None
if OPENAI_API_KEY and OpenAI:
    try:
        oa = OpenAI(api_key=OPENAI_API_KEY)
    except Exception:
        oa = None


# -------------------
# Sidebar controls
# -------------------
st.sidebar.markdown("### Tools")
if st.sidebar.button("🔄 Refresh data cache"):
    st.cache_data.clear()
    st.success("Cache cleared — reloading data…")
    st.rerun()

st.sidebar.header("Ops Controls")
auto_on = st.sidebar.toggle("Auto-refresh", value=True, help="Refresh this page automatically.")
every = st.sidebar.slider("Refresh interval (seconds)", 30, 900, REFRESH_SECS_DEFAULT, 15)
if auto_on:
    auto_refresh_meta(every)

# housekeeping buttons
st.sidebar.markdown("---")
if st.sidebar.button("🧹 Clear local logs (CSV)"):
    try:
        if LOG_CSV.exists():
            LOG_CSV.unlink()
        st.sidebar.success("Local user_reflections.csv cleared.")
    except Exception as e:
        st.sidebar.warning(f"Could not clear CSV: {e}")

if st.sidebar.button("🌱 Seed demo data"):
    seeded = False
    try:
        demo_prompts = [
            {"id": None, "theme": "Surrender", "prompt": "What are you still trying to control?"},
            {"id": None, "theme": "Clarity",   "prompt": "What truth have you been avoiding lately?"},
            {"id": None, "theme": "Presence",  "prompt": "Where could you soften toward yourself today?"},
        ]
        demo_insights = [
            {"theme": "Surrender", "insight": "Letting go lets life lead.", "mantra": "I release and trust."},
            {"theme": "Clarity",   "insight": "Truth arises when we are still.", "mantra": "I see what is."},
            {"theme": "Presence",  "insight": "The present is a sanctuary.", "mantra": "I am here now."},
        ]

        if sb:
            # upsert prompts (id generated by DB)
            sb.table("reflection_prompts").upsert(demo_prompts).execute()
            sb.table("mentor_insights").upsert(demo_insights).execute()
            seeded = True
        else:
            # CSV fallback—append uniquely
            if PROMPTS_CSV.exists():
                p = pd.read_csv(PROMPTS_CSV)
            else:
                p = pd.DataFrame(columns=["id","theme","prompt"])
            p = pd.concat([p, pd.DataFrame(demo_prompts)], ignore_index=True)
            p.to_csv(PROMPTS_CSV, index=False)

            if INSIGHTS_CSV.exists():
                i = pd.read_csv(INSIGHTS_CSV)
            else:
                i = pd.DataFrame(columns=["id","theme","insight","mantra"])
            i = pd.concat([i, pd.DataFrame(demo_insights)], ignore_index=True)
            i.to_csv(INSIGHTS_CSV, index=False)
            seeded = True

        if seeded:
            st.sidebar.success("Demo prompts & insights seeded.")
    except Exception as e:
        st.sidebar.warning(f"Seeding failed: {e}")


# -------------------
# Header & Uptime
# -------------------
st.title("🩺 System Health")

start_dt = ensure_uptime_start()
uptime = datetime.utcnow() - start_dt
st.caption(f"AGIcyborg.ai — connectivity, data & runtime status.  •  Uptime: **{format_delta(uptime)}**")


# -------------------
# Status cards
# -------------------
ok_supabase = bool(sb)
ok_openai   = bool(oa)

col1, col2, col3, col4 = st.columns([1,1,1,1])

with col1:
    st.subheader("Supabase URL")
    st.metric(label="", value="✅" if ok_supabase else "⚠️", help="Connection status")
    st.code(mask(SUPABASE_URL), language="text")

with col2:
    st.subheader("Supabase Key")
    st.metric(label="", value="🔑" if ok_supabase else "—")
    st.code(mask(SUPABASE_KEY), language="text")

with col3:
    st.subheader("OpenAI")
    st.metric(label="", value="✅" if ok_openai else "⚠️")
    st.code(mask(OPENAI_API_KEY), language="text")

with col4:
    st.subheader("Python / Streamlit")
    st.metric(label="", value=f"{platform.python_version()} / {st.__version__}")
    # Small energy pulse when both providers OK
    if ok_supabase and ok_openai:
        st.write("Energy", unsafe_allow_html=True)
        pulse(visible=True)


# -------------------
# Data status
# -------------------
st.markdown("---")
st.header("📚 Data status")

# Fetch (cached) counts
# AFTER
counts = get_counts(_sb=sb)
prompts_cnt, prompts_msg = counts["prompts"]
insights_cnt, insights_msg = counts["insights"]
reflections_cnt, reflections_msg = counts["reflections"]

# Summary metrics
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Prompts", prompts_cnt)
    st.caption(prompts_msg)
with col2:
    st.metric("Insights", insights_cnt)
    st.caption(insights_msg)
with col3:
    st.metric("Reflections", reflections_cnt)
    st.caption(reflections_msg)


# -------------------
# Prompt weighting section
# -------------------
st.markdown("----")
st.header("📊 Prompt distribution & weighting (frequency_weight)")
render_weight_health(sb, show_title=False)
render_weight_charts(sb, show_title=False)

st.markdown("---")
st.caption("Tip: Use the sidebar to seed data or clear local logs. Auto-refresh keeps this view alive.")