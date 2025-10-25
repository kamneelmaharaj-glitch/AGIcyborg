# --- imports ---
import os
from pathlib import Path
from datetime import datetime
import re

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

# Optional AI mentor
try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # if the package isn't installed, we handle gracefully

# --- page config (MUST be first Streamlit call) ---
st.set_page_config(page_title="AGIcyborg — Reflection", page_icon="🌿", layout="centered")

# =========================
#   Env & Supabase setup
# =========================
ENV_PATH = Path(__file__).with_name(".env")
load_dotenv(dotenv_path=ENV_PATH)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

sb = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
        st.sidebar.success("☁️ Connected to Supabase")
    except Exception as e:
        st.sidebar.error(f"Supabase init failed: {e}")
else:
    st.sidebar.warning("⚠️ Supabase not configured, using local CSVs")

# =========================
#   AI Mentor (OpenAI)
# =========================
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "").strip()
ai_client = None
if OPENAI_KEY and OpenAI:
    try:
        ai_client = OpenAI(api_key=OPENAI_KEY)
        st.sidebar.info("🧠 AI Mentor available")
    except Exception as e:
        st.sidebar.warning(f"AI Mentor disabled: {e}")
else:
    if not OpenAI:
        st.sidebar.warning("AI Mentor disabled: `openai` package not installed.")
    elif not OPENAI_KEY:
        st.sidebar.warning("AI Mentor disabled: no OPENAI_API_KEY in .env")

use_ai = st.sidebar.toggle(
    "AI Mentor Mode (beta)",
    value=False,
    help="Generate a personalized insight + mantra from your reflection."
) if ai_client else False

# =========================
#   Local CSV fallbacks
# =========================
DATA_DIR = Path(__file__).parent / "data"
PROMPTS_CSV = DATA_DIR / "reflection_prompts.csv"
INSIGHTS_CSV = DATA_DIR / "mentor_insights.csv"
LOG_CSV = DATA_DIR / "user_reflections.csv"

# =========================
#   THEME MAP (canonicalization)
# =========================
# map many synonyms → one canonical theme
THEME_MAP = {
    # Canonical : synonyms/aliases (all compared in lowercase)
    "Surrender": {"surrender", "let go", "release", "allowing", "trust"},
    "Clarity": {"clarity", "truth", "insight", "seeing clearly", "focus"},
    "Presence": {"presence", "now", "mindfulness", "awareness"},
    "Compassion": {"compassion", "kindness", "forgiveness", "soften"},
    "Courage": {"courage", "honesty", "bravery", "integrity"},
    "Gratitude": {"gratitude", "appreciation", "thankfulness"},
    "Patience": {"patience", "pace", "timing", "slow down"},
    # Add more as you grow
}

# Fast reverse lookup for lowercase terms → canonical
REVERSE_THEME = {}
for canon, aliases in THEME_MAP.items():
    REVERSE_THEME.update({a.lower(): canon for a in aliases})
    REVERSE_THEME[canon.lower()] = canon  # ensure canonical also maps to itself

def canonical_theme(theme: str) -> str:
    """Return canonical theme for matching/saving; fallback to original capitalization if unknown."""
    if not theme:
        return theme
    t = str(theme).strip()
    return REVERSE_THEME.get(t.lower(), t)  # unknowns pass through

# =========================
#   Loaders (cloud → local)
# =========================
def load_prompts_df() -> pd.DataFrame:
    """Reflection prompts: id, theme, prompt"""
    if sb:
        res = sb.table("reflection_prompts").select("id,theme,prompt").execute()
        return pd.DataFrame(res.data)
    return pd.read_csv(PROMPTS_CSV)

def load_insights_df() -> pd.DataFrame:
    """Mentor insights: id, theme, insight, mantra"""
    if sb:
        res = sb.table("mentor_insights").select("id,theme,insight,mantra").execute()
        return pd.DataFrame(res.data)
    return pd.read_csv(INSIGHTS_CSV)

# =========================
#   Header
# =========================
st.markdown("# 🌿 AGIcyborg — Daily Reflection")
st.caption("Awakened Guided Intelligence — Your Dharma, Amplified.")

# =========================
#   Data bootstrap
# =========================
try:
    prompts = load_prompts_df()
    if prompts.empty:
        st.warning("No prompts found. Please seed `reflection_prompts` in Supabase (or the CSV).")
        st.stop()
except Exception as e:
    st.error(f"Could not load prompts: {e}")
    st.stop()

# Helpers
def pick_next_prompt(df: pd.DataFrame) -> dict:
    """Randomly pick next reflection prompt, weighted by frequency_weight if available."""
    if "frequency_weight" in df.columns:
        weights = df["frequency_weight"].fillna(1).astype(float)
        if (weights > 0).any():
            chosen = df.sample(1, weights=weights).iloc[0].to_dict()
            st.sidebar.caption("🎲 Selected prompt **weighted** by frequency_weight")
            return chosen

    chosen = df.sample(1).iloc[0].to_dict()
    st.sidebar.caption("🎲 Selected prompt **uniformly** (no weights)")
    return chosen

    # Fallback — uniform random
    chosen = df.sample(1).iloc[0].to_dict()
    st.sidebar.caption(f"🎲 Selected prompt uniformly (no weights found)")
    return chosen

def choose_curated_insight(insights_df: pd.DataFrame, theme: str) -> dict:
    """Return a row from mentor_insights matching canonical theme or any row if none match."""
    canon = canonical_theme(theme)
    # normalize both sides for robust match
    df = insights_df.copy()
    df["_canon"] = df["theme"].astype(str).str.strip().map(canonical_theme)
    matches = df[df["_canon"].str.lower() == canon.lower()] if canon else df
    row = (matches if not matches.empty else df).sample(1).iloc[0]
    return {
        "insight": str(row.get("insight", "")).strip(),
        "mantra":  str(row.get("mantra", "")).strip(),
    }

# Session state
if "current_prompt" not in st.session_state:
    st.session_state.current_prompt = pick_next_prompt(prompts)
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "reflection_text" not in st.session_state:
    st.session_state.reflection_text = ""

prompt = st.session_state.current_prompt
canon_theme = canonical_theme(prompt.get("theme", ""))

# =========================
#   Prompt + input
# =========================
st.subheader("Your Reflection Prompt")
st.markdown(f"> **{prompt.get('prompt', '')}**")
st.caption(f"Theme: `{canon_theme}`")

st.session_state.reflection_text = st.text_area(
    "What arises within you?",
    value=st.session_state.reflection_text,
    height=150,
    placeholder="Write honestly. Small and true is enough."
)

# =========================
#   Receive Insight
# =========================
clicked = st.button(
    "Receive Insight 🌿",
    type="primary",
    disabled=(len(st.session_state.reflection_text.strip()) == 0)
)

if clicked:
    # 1) load insights cloud → local
    try:
        insights_df = load_insights_df()
        if insights_df is None or insights_df.empty:
            st.error("No mentor insights available (table or CSV empty).")
            st.stop()
    except Exception as e:
        st.error(f"Could not load insights: {e}")
        st.stop()

    # 2) choose curated row that matches canonical theme
    curated = choose_curated_insight(insights_df, canon_theme)
    shown_insight = curated["insight"]
    shown_mantra  = curated["mantra"]

    # 3) AI mentor override (optional)
    if use_ai and ai_client:
        try:
            system_msg = (
                "You are a compassionate, Dharma-aligned mentor. "
                "You speak with calm clarity and practical kindness."
            )
            user_msg = f"""
Theme: {canon_theme}
User reflection: {st.session_state.reflection_text.strip()}

Write EXACTLY two lines:
INSIGHT: <2–3 short sentences giving grounded guidance>
MANTRA: <≤ 8 words, simple and gentle>
""".strip()

            resp = ai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.7,
                max_tokens=180,
            )
            text = resp.choices[0].message.content.strip()
            m_insight = re.search(r"INSIGHT:\s*(.+)", text, re.IGNORECASE)
            m_mantra  = re.search(r"MANTRA:\s*(.+)",  text, re.IGNORECASE)
            if m_insight:
                shown_insight = m_insight.group(1).strip()
            if m_mantra:
                shown_mantra  = m_mantra.group(1).strip()
        except Exception as e:
            st.sidebar.warning(f"AI mentor unavailable, using curated insight. ({e})")

    # 4) show result
    st.session_state.last_result = {"insight": shown_insight, "mantra": shown_mantra}
    st.success("Your reflection has been received. Wisdom is listening.")
    with st.container(border=True):
        st.markdown("**Insight**")
        st.write(shown_insight)
        st.markdown("_Mantra_")
        st.write(f"*{shown_mantra}*")

    # 5) log reflection (Supabase → CSV fallback)
    entry = {
        "prompt_id": prompt.get("id"),
        "theme": canon_theme,  # save canonical theme
        "reflection_text": st.session_state.reflection_text.strip(),
        "generated_insight": shown_insight,
        "generated_mantra": shown_mantra,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    try:
        if sb:
            sb.table("user_reflections").insert(entry).execute()
            st.sidebar.success("✨ Reflection saved to Supabase")
        else:
            raise RuntimeError("no_supabase")
    except Exception as e:
        # local CSV fallback
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        header = not LOG_CSV.exists() or LOG_CSV.stat().st_size == 0
        pd.DataFrame([entry]).to_csv(LOG_CSV, mode="a", index=False, header=header)
        st.sidebar.warning(f"Saved locally (offline): {e}")

    # 6) clear input for next round
    st.session_state.reflection_text = ""

# =========================
#   Next reflection
# =========================
if st.session_state.last_result is not None:
    if st.button("Next Reflection →", type="secondary"):
        # Reload prompts (so new Supabase inserts appear without app restart)
        try:
            prompts = load_prompts_df()
        except Exception:
            pass
        st.session_state.current_prompt = pick_next_prompt(prompts)
        st.session_state.last_result = None
        st.session_state.reflection_text = ""
        st.rerun()

# =========================
#   History (cloud → local) — resilient
# =========================
with st.expander("My recent reflections"):
    try:
        if sb:
            res = (
                sb.table("user_reflections")
                .select("created_at, theme, reflection_text, generated_insight, generated_mantra")
                .order("created_at", desc=True)
                .limit(20)
                .execute()
            )
            hist = pd.DataFrame(res.data)
        else:
            hist = pd.read_csv(LOG_CSV).tail(20)

        if not hist.empty:
            cols = ["created_at", "theme", "reflection_text", "generated_insight", "generated_mantra"]
            cols = [c for c in cols if c in hist.columns]
            st.dataframe(hist[cols], use_container_width=True)
        else:
            st.info("No reflections logged yet.")
    except ImportError:
        st.warning(
            "History viewer needs NumPy/pandas but they failed to load. "
            "Try: `pip install --force-reinstall numpy==1.26.4 pandas==2.2.2`."
        )
    except Exception as e:
        st.warning(f"Could not load history: {e}")