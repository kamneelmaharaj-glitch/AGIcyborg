# app.py — AGIcyborg Reflection Space (modern, future-safe, themed)

from __future__ import annotations

import os
import re
import json
import textwrap
import random
import datetime
from typing import Dict, Any, Tuple, Optional, List

import streamlit as st
from supabase import create_client, Client

# Optional OpenAI (only used if configured)
try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
    OpenAI = None  # so local dev without openai still runs

# ----------------------------
# Page config (must be first Streamlit call)
# ----------------------------
st.set_page_config(page_title="AGIcyborg — Reflection", page_icon="🪷", layout="centered")

# ----------------------------
# Global UI styling (dark, clean, future-safe)
# ----------------------------
st.markdown("""
<style>
/* ---------- Layout & rhythm ---------- */
.block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 880px; }
section.main > div { gap: 1.25rem !important; }
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { letter-spacing: .2px; }

/* ---------- Inputs ---------- */
textarea, .stTextArea textarea { line-height: 1.5; }
.stTextInput > div > div > input { line-height: 1.5; }

/* ---------- Buttons ---------- */
button[kind="primary"] {
  border-radius: 10px; padding: .55rem 1.05rem; font-weight: 600;
}

/* ---------- Subtle divider ---------- */
.agi-divider { margin: 2rem 0 1.25rem; border-bottom: 1px solid rgba(255,255,255,.08); }

/* ---------- Form box polish ---------- */
div[data-testid="stForm"] {
  background-color: #111214;
  padding: 1.5rem;
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,.10);
}

/* ===== Mentor card — force dark, high-contrast base ===== */
.mentor-card{
  border-radius:14px;
  background-image: none !important;
  background: #0f1218 !important; /* dark base */
  border:1px solid rgba(255,255,255,.12) !important;
  padding:18px 16px; margin-top:.75rem; margin-bottom:.25rem;
  color:#e8eef6 !important;
  box-shadow: 0 1px 0 rgba(0,0,0,.3) inset, 0 8px 24px rgba(0,0,0,.25);
}
.mentor-card h4{
  margin:0 0 .6rem 0; font-weight:700;
  color:#f6f8fb !important;
  text-shadow: 0 1px 2px rgba(0,0,0,.30);
}
.mentor-card p{ margin:.35rem 0; }
.mentor-card p strong{ color:#ffd6df !important; }  /* insight emphasis */
.mentor-card p em{ color:#c7d1dc !important; }      /* mantra */

/* Smooth reveal */
.mentor-card.reveal { opacity:0; transform: translateY(6px); animation: agiFadeIn .45s ease-out forwards; }
@keyframes agiFadeIn { to { opacity:1; transform: translateY(0); } }

/* ===== Subtle per-theme tints (keep contrast) ===== */
.mentor-card.theme-Clarity{
  background:
    linear-gradient(135deg, rgba(100,180,255,.10), rgba(140,170,255,.07)) , #0f1218 !important;
}
.mentor-card.theme-Compassion{
  background:
    linear-gradient(135deg, rgba(255,150,190,.12), rgba(255,180,210,.07)) , #0f1218 !important;
}
.mentor-card.theme-Courage{
  background:
    linear-gradient(135deg, rgba(255,190,120,.10), rgba(255,170,90,.06)) , #0f1218 !important;
}
.mentor-card.theme-Presence{
  background:
    linear-gradient(135deg, rgba(64,224,208,.12), rgba(150,140,255,.07)) , #0f1218 !important;
}
.mentor-card.theme-Surrender{
  background:
    linear-gradient(135deg, rgba(120,235,170,.12), rgba(120,200,180,.06)) , #0f1218 !important;
}
/* "Calm Sage" gets sanitized to Calm-Sage in class names */
.mentor-card.theme-Calm-Sage{
  background:
    linear-gradient(135deg, rgba(160,210,255,.12), rgba(170,200,255,.07)) , #0f1218 !important;
}

/* Optional hover glow */
.mentor-card.theme-Clarity:hover    { box-shadow: 0 0 24px rgba(109,196,255,.18); }
.mentor-card.theme-Compassion:hover { box-shadow: 0 0 24px rgba(255,152,194,.18); }
.mentor-card.theme-Courage:hover    { box-shadow: 0 0 24px rgba(255,184,77,.18);  }
.mentor-card.theme-Presence:hover   { box-shadow: 0 0 24px rgba(172,160,255,.18); }
.mentor-card.theme-Surrender:hover  { box-shadow: 0 0 24px rgba(140,224,170,.18); }
.mentor-card.theme-Calm-Sage:hover  { box-shadow: 0 0 24px rgba(180,220,255,.18); }

/* ===================== Presence banner + practice ===================== */
.presence-banner{
  background: radial-gradient(1200px 600px at -10% -10%, rgba(61, 245, 184, .08), transparent 40%),
              radial-gradient(1600px 900px at 110% 110%, rgba(132, 161, 255, .08), transparent 32%),
              linear-gradient(180deg, rgba(255, 255, 255, .04), rgba(255, 255, 255, .02));
  border: 1px solid rgba(255, 255, 255, .10);
  border-radius: 16px;
  padding: 16px;
  color:#e8edf4;
}

/* Section wrapper for the breath orb */
.presence-wrap{
  margin: 1rem 0 0.5rem 0;
  padding: 1.25rem 1.25rem 1rem 1.25rem;
  border-radius: 14px;
  background: radial-gradient(1200px 400px at 50% 0%,
              rgba(14, 122, 102, .12), rgba(14, 122, 102, .05) 45%, transparent 70%);
  border: 1px solid rgba(14,122,102,.25);
}
.presence-title{ display:flex; align-items:center; gap:.6rem; font-weight:700; letter-spacing:.2px; }
.presence-title .dot{
  width:.5rem; height:.5rem; border-radius:999px;
  background: #3cd7b6; box-shadow: 0 0 18px rgba(60,215,182,.85);
}
.presence-note{ margin:.25rem 0 1rem 1.1rem; color:rgba(255,255,255,.72); font-size:.95rem; }

/* Breathing orb */
.breath-orb{
  --size: 160px;
  width: var(--size); height: var(--size);
  margin: .25rem auto 0 auto; border-radius: 999px;
  background: radial-gradient(circle at 35% 25%, #3cd7b6 0%, #1a5d53 60%, #0a3a34 100%);
  box-shadow: 0 0 0 2px rgba(60,215,182,.25),
              0 12px 28px rgba(0,0,0,.35),
              0 0 48px rgba(60,215,182,.25) inset;
  animation: agi-breathe 6s ease-in-out infinite;
}
@keyframes agi-breathe{
  0%   { transform: scale(0.92); filter: brightness(0.95); }
  35%  { transform: scale(1.04); filter: brightness(1); }
  55%  { transform: scale(1.02); }
  100% { transform: scale(0.92); filter: brightness(0.95); }
}

/* floating lotus */
.lotus{
  width: 28px; height: 28px; line-height:28px;
  text-align:center; border-radius:999px;
  background: rgba(60,215,182,.15);
  border: 1px solid rgba(60,215,182,.35);
  box-shadow: 0 0 12px rgba(60,215,182,.45);
  animation: float 4.8s ease-in-out infinite;
  user-select:none;
}
@keyframes float{
  0%   { transform: translateY(0px); opacity:.95; }
  50%  { transform: translateY(-10px); opacity:1; }
  100% { transform: translateY(0px); opacity:.95; }
}

/* phase + helper text under orb */
.phase{ text-align:center; margin-top:.6rem; font-weight:600; color: rgba(255,255,255,.88); }
.sense{ text-align:center; margin-top:.15rem; font-size:.92rem; color: rgba(255,255,255,.68); }

/* ---------- Expander polish ---------- */
.streamlit-expanderHeader{ font-weight:600; }
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Secrets / Config (robust)
# ----------------------------
def _get_secret(name: str, default=None):
    # Streamlit secrets → env fallback
    try:
        return st.secrets[name]
    except Exception:
        return os.getenv(name, default)

def _first(names: list[str], default=None):
    for n in names:
        v = _get_secret(n)
        if v:
            return v
    return default

SUPABASE_URL         = _first(["SUPABASE_URL", "SUPABASE_PROJECT_URL"])
SUPABASE_ANON_KEY    = _first(["SUPABASE_ANON_KEY", "SUPABASE_KEY", "SUPABASE_ANON"])
SUPABASE_SERVICE_KEY = _first(["SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE"])
OPENAI_API_KEY       = _first(["OPENAI_API_KEY"])
OPENAI_PROJECT       = _first(["OPENAI_PROJECT", "OPENAI_PROJECT_ID"])  # for sk-proj-* keys

def _mask(s: Optional[str], head=6, tail=3) -> str:
    if not s:
        return "—"
    s = str(s)
    if len(s) <= head + tail + 3:
        return s
    return f"{s[:head]}…{s[-tail:]}"

# ----------------------------
# Clients (Supabase + OpenAI)
# ----------------------------
if not SUPABASE_URL:
    st.error("Missing `SUPABASE_URL`. Add it to `.streamlit/secrets.toml` or your environment.")
    st.stop()

if not (SUPABASE_ANON_KEY or SUPABASE_SERVICE_KEY):
    st.error("Missing Supabase key. Provide `SUPABASE_SERVICE_KEY` or `SUPABASE_ANON_KEY` in secrets.")
    st.stop()

sb: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY)

def _get_openai_client() -> Optional[OpenAI]:
    if not (OPENAI_API_KEY and OpenAI):
        return None
    # Support either standard key or project key (sk-proj-... + proj_...)
    if OPENAI_API_KEY.startswith("sk-proj-"):
        if not (OPENAI_PROJECT and OPENAI_PROJECT.startswith("proj_")):
            return None
        return OpenAI(api_key=OPENAI_API_KEY, project=OPENAI_PROJECT)
    return OpenAI(api_key=OPENAI_API_KEY)

# ----------------------------
# Mentor theming (Option 1 – structured voice)
# ----------------------------
THEME_PROFILES: Dict[str, Dict[str, Any]] = {
    "Clarity":    {"persona": "Sees the essential truth beneath surface noise.",
                   "voice": "Grounded, simple, luminous.", "max_words": 80,
                   "mantra_hint": "Short, clear, present-tense."},
    "Compassion": {"persona": "Notices suffering and responds with tenderness.",
                   "voice": "Soft, kind, reassuring.", "max_words": 90,
                   "mantra_hint": "Heart-softening, present-tense."},
    "Courage":    {"persona": "Calls forth brave, truthful action without force.",
                   "voice": "Calm, steady, quietly bold.", "max_words": 90,
                   "mantra_hint": "Spine-straightening, present-tense."},
    "Presence":   {"persona": "Invites stillness, sensing, and immediacy.",
                   "voice": "Spacious, slow, attentive.", "max_words": 80,
                   "mantra_hint": "Breath-anchored, here-and-now."},
    "Surrender":  {"persona": "Releases control and rests in what is.",
                   "voice": "Gentle, yielding, devotional.", "max_words": 90,
                   "mantra_hint": "Open-handed, present-tense."},
    "Calm Sage":  {"persona": "Speaks in clean lines and small truths.",
                   "voice": "Minimal, measured, unhurried.", "max_words": 70,
                   "mantra_hint": "Smooth, balanced cadence."},
}

# === Theme → color styles =====================================================
THEME_COLORS = {
    "Clarity": {
        "bg": "linear-gradient(180deg, rgba(129,178,255,.18), rgba(100,160,255,.10))",
        "border": "1px solid rgba(129,178,255,.35)",
        "accent": "#a7c4ff",
        "icon": "🕊",
    },
    "Compassion": {
        "bg": "linear-gradient(180deg, rgba(255,182,193,.18), rgba(255,170,185,.10))",
        "border": "1px solid rgba(255,182,193,.35)",
        "accent": "#ffc2cc",
        "icon": "💗",
    },
    "Courage": {
        "bg": "linear-gradient(180deg, rgba(255,193,94,.18), rgba(255,175,64,.10))",
        "border": "1px solid rgba(255,193,94,.35)",
        "accent": "#ffd89a",
        "icon": "🔥",
    },
    "Presence": {
        "bg": "linear-gradient(180deg, rgba(140,255,210,.18), rgba(100,235,195,.10))",
        "border": "1px solid rgba(140,255,210,.35)",
        "accent": "#b4ffe4",
        "icon": "🌿",
    },
    "Surrender": {
        "bg": "linear-gradient(180deg, rgba(209,173,255,.18), rgba(185,150,255,.10))",
        "border": "1px solid rgba(209,173,255,.35)",
        "accent": "#e2d1ff",
        "icon": "🫶",
    },
    "Calm Sage": {
        "bg": "linear-gradient(180deg, rgba(185,220,200,.18), rgba(160,205,185,.10))",
        "border": "1px solid rgba(185,220,200,.35)",
        "accent": "#d3efe1",
        "icon": "🧘",
    },
}

# --- Theme colors for UI (card/headers) ---
THEME_COLORS = {
    "Clarity":     ("#74EBD5", "#ACB6E5"),   # teal → soft blue
    "Compassion":  ("#FBD3E9", "#BB377D"),   # pink → plum
    "Courage":     ("#F7971E", "#FFD200"),   # amber → gold
    "Presence":    ("#00C6FF", "#0072FF"),   # cyan → deep blue
    "Surrender":   ("#C9D6FF", "#E2E2E2"),   # periwinkle → light gray
    "Calm Sage":   ("#A8E063", "#56AB2F"),   # lime → sage
}
THEME_STYLES = {
    "Clarity":    {"bg": "linear-gradient(135deg,#c9f3ff,#b8e1ff,#cbd6ff)"},
    "Compassion": {"bg": "linear-gradient(135deg,#ffd6e6,#ffc6da,#ffd5ef)"},
    "Courage":    {"bg": "linear-gradient(135deg,#ffe1b3,#ffd39a,#ffe6c8)"},
    "Presence":   {"bg": "linear-gradient(135deg,#dcd7ff,#c9c0ff,#e4dbff)"},
    "Surrender":  {"bg": "linear-gradient(135deg,#d9ffe6,#c8f7dc,#e3ffef)"},
    "Calm Sage":  {"bg": "linear-gradient(135deg,#d8f1ff,#cfe8ff,#e1f4ff)"},
}
def theme_gradient(theme: str) -> tuple[str, str]:
    """Return (start_color, end_color) for the given theme."""
    return THEME_COLORS.get(theme, ("#2b5876", "#4e4376"))  # tasteful fallback

def render_mentor_card(theme: str, insight: str, mantra: str):
    g1, g2 = theme_gradient(theme)
    st.markdown(
        f"""
        <div style="
            border-radius: 16px;
            padding: 18px 20px;
            margin-top: 8px;
            background: linear-gradient(135deg, {g1} 0%, {g2} 100%);
            color: #111;
            box-shadow: 0 8px 24px rgba(0,0,0,.25) inset, 0 4px 18px rgba(0,0,0,.15);
        ">
          <div style="font-size:15px; opacity:.95; margin-bottom:6px;">
            🕊 <strong>Mentor Insight</strong> —
            <span style="opacity:.9;">{theme}</span>
          </div>
          <div style="font-size:18px; line-height:1.5; font-weight:600;">
            {insight.strip()}
          </div>
          <div style="margin-top:10px; font-style:italic; font-size:15px;">
            {mantra.strip()}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_presence_widget(phase: str | None = None, hint: str | None = None):
    """Pretty breathing widget with soft tint + floating lotus."""
    st.markdown(
        """
        <div class="presence-wrap">
          <div class="presence-title">
            <span class="dot"></span>
            <span>Return to stillness</span>
            <span class="lotus" style="margin-left:.5rem">🪷</span>
          </div>
          <div class="presence-note">Breathe 4–2–6 and simply notice three sensations.</div>
          <div class="breath-orb"></div>
          <div class="phase">""" + (phase or "Inhale… Exhale…") + """</div>
          <div class="sense">""" + (hint or "Notice any touch, temperature, or weight.") + """</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
# ----------------------------
# AI request helpers
# ----------------------------
def _build_messages(theme: str, reflection: str) -> list:
    profile = THEME_PROFILES.get(theme, THEME_PROFILES["Clarity"])
    system = f"""
You are an Awakened Mentor for the theme "{theme}".
Persona: {profile['persona']}
Voice: {profile['voice']}
Boundaries:
- You are not a medical, legal, or crisis service; avoid clinical/diagnostic claims.
- Stay supportive and practical; do not mention being an AI.
- Use simple, grounded language; avoid clichés and spiritual bypassing.
Task:
1) Offer ONE short, practical INSIGHT (<= {profile['max_words']} words) tailored to the reflection.
2) Offer ONE MANTRA (<= 10 words) aligned with: {profile['mantra_hint']}

Return ONLY valid JSON:
{{"insight":"...", "mantra":"..."}}
"""
    user = f"""
Reflection:
{reflection.strip()}

Constraints:
- Keep the insight concrete and kind.
- Keep the mantra present-tense, breath-friendly.
- Avoid quoting the reflection; respond to it.
- No emojis.
"""
    return [
        {"role": "system", "content": textwrap.dedent(system).strip()},
        {"role": "user", "content": textwrap.dedent(user).strip()},
    ]

def _clean_json(s: str) -> Dict[str, str]:
    try:
        return json.loads(s)
    except Exception:
        m = re.search(r"\{.*\}", s, flags=re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {"insight": "", "mantra": ""}

def ai_generate(theme: str, reflection: str) -> Tuple[str, str]:
    client = _get_openai_client()
    if not client:
        raise RuntimeError("AI disabled or not configured.")
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=_build_messages(theme, reflection),
        temperature=0.4,
        max_tokens=280,
        response_format={"type": "json_object"},
    )
    raw = (resp.choices[0].message.content or "{}").strip()
    data = _clean_json(raw)
    insight = (data.get("insight") or "").strip()
    mantra  = (data.get("mantra")  or "").strip()
    if len(insight) > 400:
        insight = insight[:400].rsplit(" ", 1)[0] + "…"
    if len(mantra.split()) > 10:
        mantra = " ".join(mantra.split()[:10])
    return insight, mantra

import time

def render_presence_banner():
    st.markdown(
        """
        <div class="presence-banner">
          <strong>Presence mode:</strong> Slow down for one minute. Breathe 4–2–6 and notice three simple sensations.
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_breath_timer(seconds: int = 60):
    """
    A gentle 1-minute (default) breath cycle widget using a simple placeholder loop.
    Uses 4–2–6 pattern as text cues while the animated circle runs in CSS.
    """
    ph_title = st.empty()
    ph_cycle = st.empty()
    ph_prog  = st.empty()

    st.markdown('<div class="breath-wrap"><div class="breath"></div></div>', unsafe_allow_html=True)

    start = time.time()
    elapsed = 0
    step = 0  # 0: Inhale(4), 1: Hold(2), 2: Exhale(6)

    while elapsed < seconds:
        if step == 0:
            ph_title.markdown("**Inhale — 4**")
            for i in range(4):
                if time.time() - start >= seconds: break
                ph_cycle.write(f"{4 - i}")
                ph_prog.progress(min(1.0, (time.time() - start)/seconds))
                time.sleep(1)
            step = 1
        elif step == 1:
            ph_title.markdown("**Hold — 2**")
            for i in range(2):
                if time.time() - start >= seconds: break
                ph_cycle.write(f"{2 - i}")
                ph_prog.progress(min(1.0, (time.time() - start)/seconds))
                time.sleep(1)
            step = 2
        else:
            ph_title.markdown("**Exhale — 6**")
            for i in range(6):
                if time.time() - start >= seconds: break
                ph_cycle.write(f"{6 - i}")
                ph_prog.progress(min(1.0, (time.time() - start)/seconds))
                time.sleep(1)
            step = 0

        elapsed = time.time() - start

    ph_title.markdown("**Return to stillness**")
    ph_cycle.empty()
    ph_prog.empty()

def render_presence_micropractice():
    with st.expander("🧭 One-minute body scan (optional)"):
        a = st.checkbox("Feel the contact of your feet with the ground.")
        b = st.checkbox("Unclench jaw & soften shoulders.")
        c = st.checkbox("Notice one sound and one texture around you.")
        if st.button("Insert a Presence note into my reflection"):
            note = "Presence note: feet grounded, jaw soft, shoulders relaxed; one sound, one texture."
            prev = st.session_state.get("reflection_text", "")
            st.session_state["reflection_text"] = (prev + ("\n\n" if prev else "") + note).strip()
            st.rerun()

def render_mentor_card(theme: str, insight: str, mantra: str, anchor_id: str = "mentor_card"):
    st.markdown(
        f"""
        <div id="{anchor_id}" class="mentor-card" data-theme="{theme}">
          <h4>🕊 Mentor Insight — <span style="color:#ffb6c1;">{theme}</span></h4>
          <p><strong>{insight or ''}</strong></p>
          <p><em>{mantra or ''}</em></p>
        </div>
        """,
        unsafe_allow_html=True,
    )
def build_reflection_markdown(*, created_at=None, theme="", reflection="", insight="", mantra="", tags=None, mood=None, stillness_note=None):
    tags_line = ", ".join(tags or []) if tags else ""
    md = [
        f"# Reflection — {theme}",
        f"- **When:** {created_at or ''}",
        f"- **Mood:** {mood or '—'}",
        f"- **Tags:** {tags_line or '—'}",
        f"- **Stillness note:** {stillness_note or '—'}",
        "",
        "## Your Reflection",
        reflection.strip() or "—",
    ]
    if insight or mantra:
        md += ["", "## Mentor Insight", insight or "—", "", f"*{mantra or ''}*"]
    return "\n".join(md)
# === Guided Reflection Questions (per theme) ===========================
GUIDED_QUESTIONS = {
    "Clarity": [
        "What truth is asking to be seen today?",
        "If all distractions fell silent, what would you realize?",
        "What feels foggy, and what might bring light to it?",
        "What one small step could honor this clarity?",
    ],
    "Compassion": [
        "Who or what needs your gentleness today?",
        "Can you forgive yourself for something still lingering?",
        "What does love invite you to notice right now?",
        "How can you care without losing yourself?",
    ],
    "Courage": [
        "What fear hides beneath your hesitation?",
        "If you trusted your strength, what would you choose?",
        "What truth wants to be spoken — even softly?",
        "Where could you take one small brave step today?",
    ],
    "Presence": [
        "What sensations call your attention in this moment?",
        "If you slowed down 10%, what might you notice?",
        "Where does your mind wander when you pause?",
        "What does your breath teach you about now?",
        "What can you feel in your feet, jaw, and shoulders right now?",
        "What is the simplest true thing you can notice in this moment?"
    ],
    "Surrender": [
        "What are you still trying to control?",
        "What could you let go of — gently — today?",
        "Where is life already guiding you effortlessly?",
        "How might trust feel in your body?",
    ],
    "Calm Sage": [
        "What truth feels simple and enduring today?",
        "What wisdom whispers quietly beneath the noise?",
        "What can you release to return to balance?",
        "How does stillness speak through you right now?",
    ],
}

def get_guided_questions(theme: str, prompt_id: str, k: int = 3) -> List[str]:
    """
    Return up to k guided questions for this theme.
    - Stable for the current day (so reruns don't reshuffle).
    - Cached per-prompt in st.session_state.
    """
    pool = GUIDED_QUESTIONS.get(theme, [])
    if not pool:
        return []

    if len(pool) <= k:
        return pool

    key = f"guided_q::{prompt_id}"
    today_seed = int(datetime.date.today().strftime("%Y%m%d"))

    if key not in st.session_state:
        rnd = random.Random(hash(prompt_id) ^ today_seed)
        st.session_state[key] = rnd.sample(pool, k)

    return st.session_state[key]

def shuffle_guided_questions(prompt_id: str):
    """Force a reshuffle for the current prompt."""
    key = f"guided_q::{prompt_id}"
    if key in st.session_state:
        del st.session_state[key]

# ----------------------------
# Mentor card renderer (dark, themed, smooth-scroll)
# ----------------------------
from streamlit.components.v1 import html as _html

def render_mentor_card(
    theme: str,
    insight: str | None,
    mantra: str | None,
    anchor_id: str = "mentor_card",
) -> None:
    """
    Renders a mentor card using CSS-only theming.
    - No inline background/text color (lets .mentor-card + .theme-<Theme> CSS win)
    - Adds a theme class like 'theme-Presence' (spaces -> dashes)
    - Smooth-scrolls the viewport to the card anchor
    """
    # sanitize theme for CSS class, e.g. "Calm Sage" -> "Calm-Sage"
    theme_safe = (theme or "Clarity").strip().replace(" ", "-")

    # build the (optional) mantra block
    mantra_html = (
        f"<p><em>{mantra}</em></p>" if (mantra and mantra.strip()) else ""
    )

    st.markdown(
        f"""
        <a id="{anchor_id}"></a>
        <div class="mentor-card reveal theme-{theme_safe}" role="region" aria-label="Mentor guidance">
          <h4>🕊 Mentor Insight — <span>{theme}</span></h4>
          <p><strong>{(insight or '').strip()}</strong></p>
          {mantra_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Smooth-scroll to the card once it appears
    _html(
        f"""
        <script>
          const el = parent.document.getElementById("{anchor_id}");
          if (el) {{
            el.scrollIntoView({{ behavior: "smooth", block: "center" }});
          }}
        </script>
        """,
        height=0,
    )
# ----------------------------
# Sidebar diagnostics
# ----------------------------
with st.sidebar:
    st.markdown("### 🔎 Config")
    st.write("URL:", _mask(SUPABASE_URL))
    st.write("Anon key:", _mask(SUPABASE_ANON_KEY))
    st.write("Service key:", _mask(SUPABASE_SERVICE_KEY))
    st.write("OpenAI key:", _mask(OPENAI_API_KEY))
    st.write("OpenAI project:", OPENAI_PROJECT or "—")
    try:
        chk = sb.table("reflection_prompts").select("id", count="exact").limit(1).execute()
        st.success(f"Prompts OK: {getattr(chk, 'count', None) or '✓'}")
    except Exception as e:
        st.error(f"Prompts check failed: {e}")
    st.divider()

# ----------------------------
# Main UI
# ----------------------------
st.title("🪷 AGIcyborg Reflection Space")
st.caption("Awakened Guided Intelligence — Your Dharma, Amplified.")

# Load prompts (active only)
try:
    resp = (
        sb.table("reflection_prompts")
        .select("id, theme, prompt, active")
        .order("theme")
        .execute()
    )
    prompts = [r for r in (resp.data or []) if r.get("active", True)]
except Exception as e:
    prompts = []
    st.error(f"Could not load prompts: {e}")

if not prompts:
    st.info("No prompts yet. Seed `reflection_prompts` to begin.")
    st.stop()

# Labels & current index
labels = [
    f"{p['theme']} — {p['prompt'][:72]}{'…' if len(p['prompt']) > 72 else ''}"
    for p in prompts
]
idx = st.session_state.get("prompt_idx", 0)
idx = min(idx, len(prompts) - 1)

# ----------------------------
# Prompt selection (OUTSIDE the form)
# ----------------------------
sel_idx = st.selectbox(
    "Choose a reflection prompt",
    options=list(range(len(prompts))),
    index=idx,
    format_func=lambda i: labels[i],
    key="prompt_selectbox",
)
st.session_state["prompt_idx"] = sel_idx

selected = prompts[sel_idx]
selected_prompt_id = str(selected["id"])
selected_theme = selected["theme"]
st.session_state["current_theme"] = selected_theme  # persist across reruns

# --- Guided Question Rotation ---
import datetime, random

def get_guided_questions(theme: str, prompt_id: str, k: int = 3):
    """
    Return up to k guided questions for this theme.
    - Stable for one day.
    - Resets automatically next day.
    - Cached in session_state to avoid random reruns.
    """
    pool = GUIDED_QUESTIONS.get(theme, [])
    if not pool:
        return []

    # Make stable key (1 per prompt/theme/day)
    today = datetime.date.today().isoformat()
    key = f"guided_q::{prompt_id}::{today}"

    # Already cached?
    if key in st.session_state:
        return st.session_state[key]

    # Otherwise, build a new random sample
    rnd = random.Random(hash((prompt_id, today)))
    selected = rnd.sample(pool, k=min(k, len(pool)))
    st.session_state[key] = selected
    return selected

def shuffle_guided_questions(prompt_id: str):
    """Force a reshuffle (and persist new set for today)."""
    today = datetime.date.today().isoformat()
    for k in list(st.session_state.keys()):
        if k.startswith(f"guided_q::{prompt_id}::{today}"):
            del st.session_state[k]
# ----------------------------
# Guided questions (OUTSIDE the form)
# ----------------------------
qs = get_guided_questions(selected_theme, selected_prompt_id, k=3)
used_qs = st.session_state.get(f"used_q::{selected_prompt_id}", set())

if qs:
    st.markdown(f"#### 🪞 Guided Questions for **{selected_theme}**")

    cols = st.columns(min(3, len(qs)))
    for i, q in enumerate(qs):
        is_new = q not in used_qs
        label = f"➕ {q}" if is_new else f"✨ {q}"
        with cols[i % len(cols)]:
            if st.button(label, key=f"gqbtn::{selected_prompt_id}::{i}"):
                prev = st.session_state.get("reflection_text", "")
                st.session_state["reflection_text"] = (prev + ("\n\n" if prev else "") + q + "\n").strip()
                st.rerun()

    if st.button("🔀 Shuffle Questions", key=f"shuffle::{selected_prompt_id}"):
        shuffle_guided_questions(selected_prompt_id)
        st.rerun()

        # --- Presence Mode (only shows when theme is Presence) ---
# Presence widget (right under the Presence controls, before the reflection form)
presence_active = st.session_state.get("presence_active", False)
if presence_active:
    # If you track phase text anywhere, pass it here; otherwise it shows a good default.
    render_presence_widget(
        phase=st.session_state.get("presence_phase", None),
        hint=st.session_state.get("presence_hint", None),
    )
else:
    # Show the widget even when idle (nice, calm ambient cue)
    render_presence_widget()

# ----------------------------
# Reflection Form
# ----------------------------
with st.form("reflect_form", clear_on_submit=False):
    # Optional metadata (safe to keep inside the form)
    with st.container(border=True):
        st.caption("Optional context")

        tags_raw = st.text_input(
            "Tags (comma separated)",
            value=st.session_state.get("tags_raw", ""),
            placeholder="work, family, gratitude",
            key="tags_raw",
        )

        mood = st.select_slider(
            "Mood",
            options=["low", "steady", "open", "bright"],
            value=st.session_state.get("mood", "steady"),
            key="mood",
        )

        stillness_note = st.text_input(
            "Stillness note (what you noticed)",
            value=st.session_state.get("stillness_note", ""),
            placeholder="breath in belly, warmth in hands, texture of chair",
            key="stillness_note",
        )

    # Main reflection input
    reflection_text = st.text_area(
        "Your Reflection",
        value=st.session_state.get("reflection_text", ""),
        height=180,
        placeholder="Write honestly. Small and true is enough.",
        key="reflection_text",
    )

    use_ai = st.checkbox(
        "Generate Mentor Insight + Mantra (OpenAI)",
        value=True,
        key="use_ai",
    )

    # ✅ Required inside the form
    submitted = st.form_submit_button("Submit")

# Track used guided questions to personalize future rotations
used_key = f"used_q::{selected_prompt_id}"
if reflection_text.strip():
    prev_used = st.session_state.get(used_key, set())
    new_used = prev_used.union(set(st.session_state.get("reflection_text", "").splitlines()))
    st.session_state[used_key] = new_used

# ----------------------------
# Handle submit (OUTSIDE the form)
# ----------------------------
if submitted:
    if not reflection_text.strip():
        st.warning("Please enter a reflection before submitting.")
    else:
        generated_insight, generated_mantra = None, None
        theme_used = st.session_state.get("current_theme", selected_theme)

        if use_ai:
            try:
                with st.spinner("Invoking Mentor…"):
                    generated_insight, generated_mantra = ai_generate(theme_used, reflection_text)
            except Exception as e:
                st.warning(f"AI generation skipped: {e}")
                generated_insight, generated_mantra = None, None

        # Save to Supabase
        # Normalize tags into a list (trim empties)
        tags_list = [t.strip() for t in st.session_state.get("tags_raw", "").split(",") if t.strip()]

        row = {
            "prompt_id": selected_prompt_id,
            "theme": theme_used,
            "reflection_text": reflection_text.strip(),
            "generated_insight": generated_insight,
            "generated_mantra": generated_mantra,
            "tags": tags_list if tags_list else None,
            "mood": st.session_state.get("mood"),
            "stillness_note": st.session_state.get("stillness_note") or None,
            "source": "app",
        }
    
        try:
            ins = sb.table("user_reflections").insert(row).execute()
            if getattr(ins, "data", None):
                st.session_state["last_row_id"] = ins.data[0].get("id")

            # Persist for later use (regen + persisted mentor card)
            st.session_state["last_reflection"] = reflection_text.strip()
            st.session_state["last_theme"] = theme_used

            # ✅ Persist mentor card so it survives reruns
            st.session_state["last_mentor"] = {
                "theme": theme_used,
                "insight": generated_insight or "",
                "mantra": generated_mantra or "",
            }

            # Clear the text area on next run (do NOT mutate the widget now)
            st.session_state["clear_reflection"] = True
            st.success("Reflection saved. Thank you.")
            st.rerun()
        except Exception as e:
            st.error(f"Save failed: {e}")

# 🔁 Clear text once per request cycle (safe place)
if st.session_state.get("clear_reflection"):
    st.session_state.pop("reflection_text", None)
    st.session_state["clear_reflection"] = False

# ----------------------------
# Persisted mentor card (shows every run until dismissed)
# ----------------------------
_last = st.session_state.get("last_mentor")
if _last and (_last.get("insight") or _last.get("mantra")):
    render_mentor_card(
        _last.get("theme", "Clarity"),
        _last.get("insight", ""),
        _last.get("mantra", ""),
        anchor_id="mentor_card_last",
    )
    if st.button("Dismiss guidance", key="dismiss_last_mentor"):
        st.session_state.pop("last_mentor", None)
        st.rerun()

# Export last saved reflection as Markdown
_last = st.session_state.get("last_mentor")
if _last and (_last.get("insight") or _last.get("mantra")):
    # ... your existing render_mentor_card + Dismiss button ...

    # Build and offer a download
    md_text = build_reflection_markdown(
        created_at=None,  # we can add actual timestamp later if you like
        theme=_last.get("theme", ""),
        reflection=st.session_state.get("last_reflection", ""),
        insight=_last.get("insight", ""),
        mantra=_last.get("mantra", ""),
        tags=[t.strip() for t in st.session_state.get("tags_raw","").split(",") if t.strip()],
        mood=st.session_state.get("mood"),
        stillness_note=st.session_state.get("stillness_note"),
    )
    st.download_button(
        "⬇️ Download as Markdown",
        data=md_text.encode("utf-8"),
        file_name="reflection.md",
        mime="text/markdown",
        key="dl_md_last",
    )
# ----------------------------
# Regenerate Insight/Mantra (no duplicate save)
# ----------------------------
st.markdown("---")
st.subheader("✨ Refine Mentor Guidance")

theme_for_regen = (
    st.session_state.get("last_theme")
    or st.session_state.get("current_theme")
    or selected_theme
)

regen_reflection = st.text_area(
    "Use your last reflection (or paste a new one) to regenerate guidance.",
    value=st.session_state.get("last_reflection", ""),
    height=140,
    key="regen_text",
)
regen = st.button("Regenerate Insight (won’t save automatically)")
if regen:
    if not regen_reflection.strip():
        st.warning("Please enter text to regenerate.")
    else:
        try:
            with st.spinner("Re-centering…"):
                r_insight, r_mantra = ai_generate(theme_for_regen, regen_reflection)
            st.session_state["regen_insight"] = r_insight
            st.session_state["regen_mantra"] = r_mantra
        except Exception as e:
            st.error(f"Regeneration failed: {e}")

if st.session_state.get("regen_insight") or st.session_state.get("regen_mantra"):
    render_mentor_card(
        theme_for_regen,
        st.session_state.get("regen_insight"),
        st.session_state.get("regen_mantra"),
        anchor_id="mentor_card_regen",
    )
    if st.button("Save this regenerated guidance"):
        try:
            sb.table("user_reflections").insert({
                "prompt_id": selected_prompt_id,
                "theme": theme_for_regen,
                "reflection_text": regen_reflection.strip(),
                "generated_insight": st.session_state.get("regen_insight"),
                "generated_mantra": st.session_state.get("regen_mantra"),
            }).execute()
            st.success("Regenerated guidance saved.")
        except Exception as e:
            st.error(f"Save failed: {e}")

# ----------------------------
# Recent Reflections (paged)
# ----------------------------
st.markdown("---")
st.subheader("🕊️ Recent Reflections")

PAGE_SIZE = 10
page = st.session_state.get("page", 0)

def load_recent(page: int):
    base_cols = ["created_at", "theme", "reflection_text", "generated_insight", "generated_mantra"]
    optional_cols = ["tags", "tags_raw", "mood", "stillness_note"]

    # try full set first
    cols = base_cols + optional_cols
    try:
        res = (
            sb.table("user_reflections")
            .select(", ".join(cols))
            .order("created_at", desc=True)
            .range(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE - 1)
            .execute()
        )
        return res.data or [], set(cols)
    except Exception as e:
        # On 42703 (undefined_column) or any select error, fall back to base cols
        try:
            res = (
                sb.table("user_reflections")
                .select(", ".join(base_cols))
                .order("created_at", desc=True)
                .range(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE - 1)
                .execute()
            )
            return res.data or [], set(base_cols)
        except Exception as e2:
            st.info(f"Could not load history: {e2}")
            return [], set()

rows, available = load_recent(page)

if not rows and page == 0:
    st.caption("No reflections yet — your first one will appear here.")
else:
    for r in rows:
        # header + main text
        st.write(f"**{r.get('created_at','')} — {r.get('theme','')}**")
        st.write(r.get("reflection_text", ""))

        # optional metadata (show only if present in this table AND value exists)
        meta_bits = []

        if "mood" in available and r.get("mood"):
            meta_bits.append(f"🧭 {r['mood']}")
        if "stillness_note" in available and r.get("stillness_note"):
            meta_bits.append(f"🫧 {r['stillness_note']}")

        # prefer 'tags' (array/json) else 'tags_raw' (csv text)
        tags_val = None
        if "tags" in available and r.get("tags"):
            tags_val = r.get("tags")
        elif "tags_raw" in available and r.get("tags_raw"):
            tags_val = r.get("tags_raw")

        if tags_val:
            if isinstance(tags_val, list):
                meta_bits.append("🏷️ " + ", ".join(map(str, tags_val)))
            else:
                meta_bits.append("🏷️ " + str(tags_val))

        if meta_bits:
            st.caption(" • ".join(meta_bits))

        # mentor notes
        if r.get("generated_insight") or r.get("generated_mantra"):
            with st.expander("Mentor Notes"):
                if r.get("generated_insight"):
                    st.markdown(f"**Insight:** {r['generated_insight']}")
                if r.get("generated_mantra"):
                    st.markdown(f"**Mantra:** _{r['generated_mantra']}_")
        st.markdown("---")

    # pagination
    c1, _, c3 = st.columns(3)
    if c1.button("◀︎ Prev", disabled=(page == 0)):
        st.session_state["page"] = max(0, page - 1)
        st.rerun()
    if c3.button("Next ▶︎", disabled=(len(rows) < PAGE_SIZE)):
        st.session_state["page"] = page + 1
        st.rerun()