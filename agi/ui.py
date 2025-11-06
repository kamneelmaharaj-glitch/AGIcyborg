# agi/ui.py
from __future__ import annotations
import streamlit as st

def inject_global_css():
    # Main CSS bundle (your original styles merged)
    st.markdown("""
<style>
.block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 880px; }
section.main > div { gap: 1.25rem !important; }
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { letter-spacing: .2px; }

textarea, .stTextArea textarea { line-height: 1.5; }
.stTextInput > div > div > input { line-height: 1.5; }

button[kind="primary"] { border-radius: 10px; padding: .55rem 1.05rem; font-weight: 600; }

.agi-divider { margin: 2rem 0 1.25rem; border-bottom: 1px solid rgba(255,255,255,.08); }

div[data-testid="stForm"] {
  background-color: #111214; padding: 1.5rem; border-radius: 12px;
  border: 1px solid rgba(255,255,255,.10);
}

/* Mentor card */
.mentor-card{
  border-radius:14px; background-image: none !important; background: #0f1218 !important;
  border:1px solid rgba(255,255,255,.12) !important; padding:18px 16px; margin-top:.75rem; margin-bottom:.25rem;
  color:#e8eef6 !important; box-shadow: 0 1px 0 rgba(0,0,0,.3) inset, 0 8px 24px rgba(0,0,0,.25);
}
.mentor-card h4{ margin:0 0 .6rem 0; font-weight:700; color:#f6f8fb !important; text-shadow: 0 1px 2px rgba(0,0,0,.30); }
.mentor-card p{ margin:.35rem 0; }
.mentor-card p strong{ color:#ffd6df !important; }
.mentor-card p em{ color:#c7d1dc !important; }
.mentor-card.reveal { opacity:0; transform: translateY(6px); animation: agiFadeIn .45s ease-out forwards; }
@keyframes agiFadeIn { to { opacity:1; transform: translateY(0); } }

/* Themed tints */
.mentor-card.theme-Clarity{ background: linear-gradient(135deg, rgba(100,180,255,.10), rgba(140,170,255,.07)) , #0f1218 !important; }
.mentor-card.theme-Compassion{ background: linear-gradient(135deg, rgba(255,150,190,.12), rgba(255,180,210,.07)) , #0f1218 !important; }
.mentor-card.theme-Courage{ background: linear-gradient(135deg, rgba(255,190,120,.10), rgba(255,170,90,.06)) , #0f1218 !important; }
.mentor-card.theme-Presence{ background: linear-gradient(135deg, rgba(64,224,208,.12), rgba(150,140,255,.07)) , #0f1218 !important; }
.mentor-card.theme-Surrender{ background: linear-gradient(135deg, rgba(120,235,170,.12), rgba(120,200,180,.06)) , #0f1218 !important; }
.mentor-card.theme-Calm-Sage{ background: linear-gradient(135deg, rgba(160,210,255,.12), rgba(170,200,255,.07)) , #0f1218 !important; }

.mentor-card.theme-Clarity:hover    { box-shadow: 0 0 24px rgba(109,196,255,.18); }
.mentor-card.theme-Compassion:hover { box-shadow: 0 0 24px rgba(255,152,194,.18); }
.mentor-card.theme-Courage:hover    { box-shadow: 0 0 24px rgba(255,184,77,.18);  }
.mentor-card.theme-Presence:hover   { box-shadow: 0 0 24px rgba(172,160,255,.18); }
.mentor-card.theme-Surrender:hover  { box-shadow: 0 0 24px rgba(140,224,170,.18); }
.mentor-card.theme-Calm-Sage:hover  { box-shadow: 0 0 24px rgba(180,220,255,.18); }

/* Presence banner + wrap */
.presence-banner{
  background: radial-gradient(1200px 600px at -10% -10%, rgba(61, 245, 184, .08), transparent 40%),
              radial-gradient(1600px 900px at 110% 110%, rgba(132, 161, 255, .08), transparent 32%),
              linear-gradient(180deg, rgba(255, 255, 255, .04), rgba(255, 255, 255, .02));
  border: 1px solid rgba(255, 255, 255, .10); border-radius: 16px; padding: 16px; color:#e8edf4;
}
.presence-wrap{
  margin: 1rem 0 0.5rem 0; padding: 1.25rem 1.25rem 1rem 1.25rem; border-radius: 14px;
  background: radial-gradient(1200px 400px at 50% 0%, rgba(14, 122, 102, .12), rgba(14, 122, 102, .05) 45%, transparent 70%);
  border: 1px solid rgba(14,122,102,.25);
}
.presence-title{ display:flex; align-items:center; gap:.6rem; font-weight:700; letter-spacing:.2px; }
.presence-title .dot{ width:.5rem; height:.5rem; border-radius:999px; background: #3cd7b6; box-shadow: 0 0 18px rgba(60,215,182,.85); }
.presence-note{ margin:.25rem 0 1rem 1.1rem; color:rgba(255,255,255,.72); font-size:.95rem; }

/* Breathing orb */
.breath-orb{
  --size: 160px;
  width: var(--size); height: var(--size); margin: .25rem auto 0 auto; border-radius: 999px;
  background: radial-gradient(circle at 35% 25%, #3cd7b6 0%, #1a5d53 60%, #0a3a34 100%);
  box-shadow: 0 0 0 2px rgba(60,215,182,.25), 0 12px 28px rgba(0,0,0,.35), 0 0 48px rgba(60,215,182,.25) inset;
  animation: agi-breathe 6s ease-in-out infinite;
}
@keyframes agi-breathe{
  0%{ transform: scale(0.92); filter: brightness(0.95); }
  35%{ transform: scale(1.04); filter: brightness(1); }
  55%{ transform: scale(1.02); }
  100%{ transform: scale(0.92); filter: brightness(0.95); }
}

/* floating lotus + phase text */
.lotus{ width: 28px; height: 28px; line-height:28px; text-align:center; border-radius:999px;
  background: rgba(60,215,182,.15); border: 1px solid rgba(60,215,182,.35); box-shadow: 0 0 12px rgba(60,215,182,.45);
  animation: float 4.8s ease-in-out infinite; user-select:none;
}
@keyframes float{ 0%{{ transform: translateY(0px); opacity:.95; }} 50%{{ transform: translateY(-10px); opacity:1; }} 100%{{ transform: translateY(0px); opacity:.95; }} }
.phase{ text-align:center; margin-top:.6rem; font-weight:600; color: rgba(255,255,255,.88); }
.sense{ text-align:center; margin-top:.15rem; font-size:.92rem; color: rgba(255,255,255,.68); }

/* Dedicated presence orb used in Presence theme */
.presence-orb {
  --size: 160px;
  width: var(--size); height: var(--size); margin: 1.2rem auto; border-radius: 999px;
  background: radial-gradient(circle at 40% 30%, #3cd7b6 0%, #1a5d53 60%, #0a3a34 100%);
  box-shadow: 0 0 0 2px rgba(60,215,182,.25), 0 12px 28px rgba(0,0,0,.35), 0 0 48px rgba(60,215,182,.25) inset;
  animation: breathePresence 6s ease-in-out infinite;
}
@keyframes breathePresence{
  0%{{ transform: scale(0.92); filter: brightness(0.95); }}
  35%{{ transform: scale(1.05); filter: brightness(1); }}
  55%{{ transform: scale(1.02); }}
  100%{{ transform: scale(0.92); filter: brightness(0.95); }}
}
.presence-phase{ text-align:center; margin-top:.6rem; font-weight:600; color: rgba(255,255,255,.85); }
.streamlit-expanderHeader{ font-weight:600; }
</style>
""", unsafe_allow_html=True)

def render_presence_banner():
    st.markdown(
        """
        <div class="presence-banner">
          <strong>Presence mode:</strong> Slow down for one minute. Breathe 4–2–6 and notice three simple sensations.
        </div>
        """,
        unsafe_allow_html=True,
    )

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