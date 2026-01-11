# agi/ui.py — CLEAN DROP-IN REPLACEMENT
from __future__ import annotations
import streamlit as st

def inject_global_css():
    st.markdown("""
<style>
/* ----------------------------------------------------
   GLOBAL LAYOUT
---------------------------------------------------- */
.block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 880px; }
section.main > div { gap: 1.25rem !important; }
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { letter-spacing: .2px; }

textarea, .stTextArea textarea { line-height: 1.5; }
.stTextInput > div > div > input { line-height: 1.5; }

button[kind="primary"] {
  border-radius: 10px;
  padding: .55rem 1.1rem;
  font-weight: 600;
  letter-spacing: .02em;

  /* Calm teal gradient + border */
  background:
    radial-gradient(circle at 0% 0%, rgba(60,215,182,.35), transparent 55%),
    linear-gradient(135deg, #31bfa4, #1b7f70);
  color: #f5f9ff;
  border: 1px solid rgba(60,215,182,.65);

  /* Slight depth + soft glow */
  box-shadow:
    0 0 0 1px rgba(0,0,0,.55),
    0 10px 22px rgba(0,0,0,.65),
    0 0 26px rgba(60,215,182,.10);

  cursor: pointer;

  /* Smooth interactions */
  transition:
    transform .08s ease-out,
    box-shadow .16s ease-out,
    filter .16s ease-out,
    background .22s ease-out;
}

/* Hover: gentle lift + brighter glow */
button[kind="primary"]:hover {
  box-shadow:
    0 0 0 1px rgba(0,0,0,.6),
    0 14px 28px rgba(0,0,0,.75),
    0 0 32px rgba(60,215,182,.25);
  filter: brightness(1.03);
  transform: translateY(-1px);
}

/* Pressed: soft “press in” feel */
button[kind="primary"]:active {
  transform: translateY(1px) scale(.97);
  box-shadow:
    0 0 0 1px rgba(0,0,0,.7),
    0 6px 16px rgba(0,0,0,.85),
    0 0 18px rgba(60,215,182,.18);
  filter: brightness(.98);
}

/* Keyboard focus outline – subtle but visible */
button[kind="primary"]:focus-visible {
  outline: 2px solid rgba(60,215,182,.85);
  outline-offset: 2px;
}

.agi-divider {
  margin: 2rem 0 1.25rem;
  border-bottom: 1px solid rgba(255,255,255,.08);
}

div[data-testid="stForm"] {
  background-color: #111214;
  padding: 1.5rem;
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,.10);
}

/* ----------------------------------------------------
   MENTOR CARD
---------------------------------------------------- */
.mentor-card {
  border-radius:14px;
  background:#0f1218 !important;
  border:1px solid rgba(255,255,255,.12) !important;
  padding:18px 16px;
  margin-top:.75rem;
  margin-bottom:.25rem;
  color:#e8eef6 !important;
  box-shadow:0 1px 0 rgba(0,0,0,.3) inset, 0 8px 24px rgba(0,0,0,.25);
}
.mentor-card h4 {
  margin:0 0 .6rem 0;
  font-weight:700;
  color:#f6f8fb !important;
  text-shadow:0 1px 2px rgba(0,0,0,.30);
}
.mentor-card.reveal { opacity:0; transform: translateY(6px); animation: agiFadeIn .45s ease-out forwards; }

@keyframes agiFadeIn { to { opacity:1; transform: translateY(0); }}

/* Tints for mentor */
.mentor-card.theme-Clarity{    background: linear-gradient(135deg, rgba(100,180,255,.10), rgba(140,170,255,.07)) , #0f1218 !important; }
.mentor-card.theme-Compassion{ background: linear-gradient(135deg, rgba(255,150,190,.12), rgba(255,180,210,.07)) , #0f1218 !important; }
.mentor-card.theme-Courage{    background: linear-gradient(135deg, rgba(255,190,120,.10), rgba(255,170,90,.06)) , #0f1218 !important; }
.mentor-card.theme-Presence{   background: linear-gradient(135deg, rgba(64,224,208,.12),  rgba(150,140,255,.07)) , #0f1218 !important; }
.mentor-card.theme-Surrender{  background: linear-gradient(135deg, rgba(120,235,170,.12), rgba(120,200,180,.06)) , #0f1218 !important; }
.mentor-card.theme-Calm-Sage{  background: linear-gradient(135deg, rgba(160,210,255,.12), rgba(170,200,255,.07)) , #0f1218 !important; }

/* ----------------------------------------------------
   DEEPEN MENTOR — AI CARD
---------------------------------------------------- */
.deepen-ai-card {
  border-radius: 14px;
  padding: 14px 14px 12px 14px;
  margin-top: .25rem;
  background: radial-gradient(circle at 0% 0%, rgba(160,210,255,.10), transparent 55%),
              radial-gradient(circle at 100% 100%, rgba(120,255,200,.08), transparent 55%),
              #0b0f16;
  border: 1px solid rgba(255,255,255,.14);
  box-shadow: 0 10px 26px rgba(0,0,0,.55);
  color:#e8eef6;
  font-size:.92rem;
}
.deepen-ai-card-header {
  font-size:.76rem;
  letter-spacing:.16em;
  text-transform:uppercase;
  opacity:.78;
  margin-bottom:.35rem;
}
.deepen-ai-card-theme {
  font-weight:600;
  font-size:.9rem;
  opacity:.9;
  margin-bottom:.35rem;
}
.deepen-ai-card-section-label {
  font-size:.8rem;
  text-transform:uppercase;
  letter-spacing:.12em;
  opacity:.78;
  margin-top:.35rem;
}
.deepen-ai-card p {
  margin:.15rem 0;
}

/* Theme tints for deepen card */
.deepen-ai-card.theme-Clarity{
  background: linear-gradient(135deg, rgba(120,185,255,.16), rgba(16,24,40,1));
}
.deepen-ai-card.theme-Compassion{
  background: linear-gradient(135deg, rgba(255,170,210,.18), rgba(20,14,26,1));
}
.deepen-ai-card.theme-Courage{
  background: linear-gradient(135deg, rgba(255,205,135,.20), rgba(31,20,10,1));
}
.deepen-ai-card.theme-Presence{
  background: linear-gradient(135deg, rgba(120,235,210,.20), rgba(10,24,26,1));
}
.deepen-ai-card.theme-Surrender{
  background: linear-gradient(135deg, rgba(135,235,175,.20), rgba(12,26,18,1));
}
.deepen-ai-card.theme-Calm-Sage{
  background: linear-gradient(135deg, rgba(175,215,255,.18), rgba(12,18,28,1));
}

/* Wrapper to keep the Deepen card nicely narrow on the right */
.deepen-ai-card-wrapper {
  max-width: 260px;
  margin-left: auto;
}

/* Soft fade-in for the AI card */
.deepen-ai-card.fade-in {
  animation: deepenFadeIn .45s ease-out;
}

@keyframes deepenFadeIn {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ----------------------------------------------------
   TODAY MICRO-STEP CARD
---------------------------------------------------- */

/* Main micro-step card */
.micro-card {
  border-radius: 14px;
  padding: 0.9rem 1.1rem 0.95rem 1.1rem;
  margin-top: 0.5rem;
  border: 1px solid rgba(255,255,255,.12);
  background: rgba(9,11,16,.96);
  box-shadow: 0 10px 26px rgba(0,0,0,.55);
}


/* Class that actually triggers the animation */
.micro-card.pop-in {
  animation: microCardPop 0.6s cubic-bezier(.16,.8,.19,1) forwards;
  will-change: transform, box-shadow, opacity;
}

/* Theme tints */
.micro-card.theme-Clarity{
  background: linear-gradient(135deg, rgba(120,185,255,.18), rgba(9,11,16,.96));
}
.micro-card.theme-Compassion{
  background: linear-gradient(135deg, rgba(255,170,210,.20), rgba(18,10,18,.96));
}
.micro-card.theme-Courage{
  background: linear-gradient(135deg, rgba(255,205,135,.22), rgba(22,14,8,.96));
}
.micro-card.theme-Presence{
  background: linear-gradient(135deg, rgba(120,235,210,.20), rgba(8,18,18,.96));
}
.micro-card.theme-Surrender{
  background: linear-gradient(135deg, rgba(135,235,175,.20), rgba(8,18,12,.96));
}
.micro-card.theme-Calm-Sage{
  background: linear-gradient(135deg, rgba(175,215,255,.20), rgba(8,12,20,.96));
}


/* Header pill (Due / Completed / Not set) */
.micro-pill {
  font-size: .70rem;
  text-transform: uppercase;
  letter-spacing: .16em;
  padding: .16rem .70rem;
  border-radius: 999px;
  display: inline-block;
  white-space: nowrap;
}

/* Pill states */
.micro-pill-due {
  border: 1px solid rgba(255,215,160,.70);
  background: rgba(255,215,160,.12);
  color: rgba(255,240,210,.96);
}
.micro-pill-done {
  border: 1px solid rgba(120,255,200,.80);
  background: rgba(60,215,182,.16);
  color: rgba(220,255,245,.96);
}
.micro-pill-empty {
  border: 1px dashed rgba(255,255,255,.40);
  background: rgba(255,255,255,.03);
  color: rgba(255,255,255,.78);
}
/* ----------------------------------------------------
   FIX MICRO-HEADER ALIGNMENT (TITLE & PILL LEFT)
---------------------------------------------------- */

.micro-header {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: flex-start !important;   /* LEFT aligns both title + pill */
  gap: 1rem;                                /* spacing between title & pill */
  margin-bottom: .55rem;
}

.micro-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: rgba(255,255,255,.96);
}

.micro-pill {
  margin-top: 3px;                          /* vertically centers pill */
}
/* “Why this matters” line + lotus */
.micro-why-line {
  color: rgba(255,255,255,.76);
  font-size: .9rem;
  margin-top: .4rem;
  display: flex;
  align-items: center;
  gap: .25rem;
}
.micro-lotus {
  display: inline-block;
  animation: floatLotus 4.8s ease-in-out infinite;
  font-size: 1rem;
}
/* Add spacing between the top bar and the pill */
.micro-header-pill {
  margin-top: 0.55rem;   /* adjust 0.45–0.75 depending on how much air you want */
  margin-bottom: 0.35rem;
}
                
/* ----------------------------------------------------
   GUIDED QUESTIONS — SIDEBAR CARD
---------------------------------------------------- */

.guided-qs-card {
  border-radius: 14px;
  padding: 0.9rem 0.9rem 0.85rem 0.9rem;
  margin-top: 0.35rem;
  background: radial-gradient(circle at 0% 0%, rgba(160,210,255,.12), transparent 55%),
              radial-gradient(circle at 120% 140%, rgba(120,255,200,.10), transparent 55%),
              #0b0f16;
  border: 1px solid rgba(255,255,255,.15);
  box-shadow: 0 10px 26px rgba(0,0,0,.55);
  color: #e8eef6;
  font-size: .9rem;
}

/* Theme tint hook if you want to adjust per theme later */
.guided-qs-card.theme-Clarity {
  background: linear-gradient(145deg, rgba(120,185,255,.18), rgba(11,15,22,1));
}
.guided-qs-card.theme-Compassion {
  background: linear-gradient(145deg, rgba(255,170,210,.20), rgba(20,14,26,1));
}
.guided-qs-card.theme-Courage {
  background: linear-gradient(145deg, rgba(255,205,135,.22), rgba(31,20,10,1));
}
.guided-qs-card.theme-Presence {
  background: linear-gradient(145deg, rgba(120,235,210,.20), rgba(10,24,26,1));
}
.guided-qs-card.theme-Surrender {
  background: linear-gradient(145deg, rgba(135,235,175,.20), rgba(12,26,18,1));
}
.guided-qs-card.theme-Calm-Sage {
  background: linear-gradient(145deg, rgba(175,215,255,.20), rgba(12,18,28,1));
}

.guided-qs-header {
  font-size: .76rem;
  letter-spacing: .16em;
  text-transform: uppercase;
  opacity: .78;
  margin-bottom: .25rem;
}

.guided-qs-theme-label {
  font-size: .82rem;
  font-weight: 600;
  opacity: .92;
  margin-bottom: .35rem;
}

.guided-qs-note {
  font-size: .82rem;
  opacity: .78;
  margin-bottom: .45rem;
}

.guided-qs-card .guided-q-btn-wrap {
  margin-bottom: .35rem;
}

/* Style only buttons inside the guided card */
.guided-qs-card .guided-q-btn-wrap button {
  width: 100%;
  justify-content: flex-start;
  text-align: left;
  font-size: .86rem;
  padding: .35rem .65rem;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,.12);
  background: rgba(255,255,255,.02);
  color: #e8eef6;
  transition: background .15s ease-out, border-color .15s ease-out,
              transform .10s ease-out, box-shadow .10s ease-out;
}

.guided-qs-card .guided-q-btn-wrap button:hover {
  background: rgba(120,185,255,.12);
  border-color: rgba(160,210,255,.60);
  transform: translateY(-1px);
  box-shadow: 0 0 0 1px rgba(160,210,255,.40);
}

.guided-qs-card .guided-q-btn-wrap button:active {
  transform: translateY(0);
  box-shadow: none;
}                
/* ----------------------------------------------------
   PRESENCE MODE STATIC WRAP
---------------------------------------------------- */
.presence-wrap {
  margin: 1rem 0 .5rem 0;
  padding: 1.25rem 1.25rem 1rem 1.25rem;
  border-radius:14px;
  background: radial-gradient(1200px 400px at 50% 0%, rgba(14,122,102,.12), rgba(14,122,102,.05) 45%, transparent 70%);
  border:1px solid rgba(14,122,102,.25);
}

.presence-title { display:flex; align-items:center; gap:.6rem; font-weight:700; }
.presence-title .dot {
  width:.5rem; height:.5rem;
  border-radius:999px;
  background:#3cd7b6;
  box-shadow:0 0 18px rgba(60,215,182,.85);
}
.presence-note { margin:.25rem 0 1rem 1.1rem; color:rgba(255,255,255,.72); font-size:.95rem; }

/* ----------------------------------------------------
   TODAY ORB (breath-orb)
---------------------------------------------------- */
.breath-orb {
  --size: 160px;
  width:var(--size);
  height:var(--size);
  margin:.25rem auto 0 auto;
  border-radius:999px;
  background: radial-gradient(circle at 35% 25%, #3cd7b6 0%, #1a5d53 60%, #0a3a34 100%);
  box-shadow:0 0 0 2px rgba(60,215,182,.25), 0 12px 28px rgba(0,0,0,.35),
             0 0 48px rgba(60,215,182,.25) inset;
  animation-name: agi-breathe;
  animation-duration: 6s;
  animation-timing-function: ease-in-out;
  animation-iteration-count: infinite;
}

@keyframes agi-breathe {
  0%   { transform:scale(0.92); filter:brightness(0.95); }
  35%  { transform:scale(1.04); filter:brightness(1); }
  55%  { transform:scale(1.02); }
  100% { transform:scale(0.92); filter:brightness(0.95); }
}

/* ----------------------------------------------------
   PRESENCE ORB (when Presence Signal ON)
---------------------------------------------------- */
.presence-orb {
  --size: 160px;
  width:var(--size);
  height:var(--size);
  margin:1.2rem auto;
  border-radius:999px;
  background: radial-gradient(circle at 40% 30%, #3cd7b6 0%, #1a5d53 60%, #0a3a34 100%);
  box-shadow:0 0 0 2px rgba(60,215,182,.25), 0 12px 28px rgba(0,0,0,.35),
             0 0 48px rgba(60,215,182,.25) inset;
  animation-name: breathePresence;
  animation-duration: 6s;
  animation-timing-function: ease-in-out;
  animation-iteration-count: infinite;
}

@keyframes breathePresence {
  0%   { transform:scale(0.92); filter:brightness(0.95); }
  35%  { transform:scale(1.05); filter:brightness(1); }
  55%  { transform:scale(1.02); }
  100% { transform:scale(0.92); filter:brightness(0.95); }
}

/* ----------------------------------------------------
   FLOATING LOTUS
---------------------------------------------------- */
.lotus {
  width:28px; height:28px; line-height:28px;
  text-align:center; border-radius:999px;
  background:rgba(60,215,182,.15);
  border:1px solid rgba(60,215,182,.35);
  box-shadow:0 0 12px rgba(60,215,182,.45);
  animation: floatLotus 4.8s ease-in-out infinite;
}
@keyframes floatLotus {
  0%   { transform:translateY(0px);  opacity:.95; }
  50%  { transform:translateY(-10px); opacity:1; }
  100% { transform:translateY(0px);  opacity:.95; }
}

.phase { text-align:center; margin-top:.6rem; font-weight:600; color:rgba(255,255,255,.88); }
.sense { text-align:center; margin-top:.15rem; font-size:.92rem; color:rgba(255,255,255,.68); }

.presence-phase { text-align:center; margin-top:.6rem; font-weight:600; color:rgba(255,255,255,.85); }

.streamlit-expanderHeader { font-weight:600; }

/* ----------------------------------------------------
   Reflection header (Minimal Calm)
---------------------------------------------------- */
.reflection-helper {
  font-size: .9rem;
  color: rgba(255,255,255,.65);
  margin: .15rem 0 .45rem 0;
}
.gq-helper {
  margin-top: .15rem;
  margin-bottom: .45rem;
  font-size: .88rem;
  color: rgba(255,255,255,.70);
}
.reflect-header {
  margin: 1.25rem 0 0.5rem 0;
  padding: 1rem 1.1rem;
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.22) !important;
  background: rgba(18, 21, 26, 0.66);
  backdrop-filter: blur(6px);
  position: relative;
  z-index: 10;
}

.reflect-header-top {
  display: flex;
  align-items: center;
  gap: .5rem;
  margin-bottom: .35rem;
}

.reflect-header-top .pill {
  font-size: .78rem;
  text-transform: uppercase;
  letter-spacing: .14em;
  padding: .12rem .6rem;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,.18);
  background: rgba(255,255,255,.02);
  opacity: .9;
}

.reflect-header-top .theme {
  font-weight: 600;
  font-size: .9rem;
  opacity: .9;
}

.reflect-header .prompt {
  font-size: 1.05rem;
  line-height: 1.55;
  opacity: .92;
}
/* ----------------------------------------------------
   Last reflection highlight card above the trend chart
---------------------------------------------------- */
.energy-last-reflection {
  position: relative;
  margin: 0 0 18px 0;
  padding: 20px 24px 20px 24px;
  border-radius: 24px;

  /* Soft gradient + glow */
  background: radial-gradient(circle at 0% 0%, #5764ff 0%, #171b30 55%, #050712 100%);
  box-shadow:
    0 0 0 1px rgba(143, 188, 255, 0.35),
    0 22px 40px rgba(0, 0, 0, 0.72),
    0 0 60px rgba(92, 134, 255, 0.55);
  overflow: hidden;
}

.energy-last-reflection::before {
  content: "";
  position: absolute;
  inset: -40%;
  background: radial-gradient(circle at 0% 0%, rgba(156, 214, 255, 0.40), transparent 55%);
  mix-blend-mode: screen;
  opacity: 0.95;
  pointer-events: none;
}

/* Content styling */
.energy-last-reflection__meta {
  font-size: 0.8rem;
  opacity: 0.8;
  margin-bottom: 4px;
}

.energy-last-reflection__title {
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 4px;
}

.energy-last-reflection__stats {
  font-size: 0.9rem;
  opacity: 0.85;
  margin-bottom: 12px;
}

.energy-last-reflection__stats span {
  font-weight: 600;
}

.energy-last-reflection__body {
  font-size: 0.95rem;
  line-height: 1.5;
  margin-bottom: 10px;
}

.energy-last-reflection__hint {
  font-size: 0.85rem;
  color: #8be9a8;
  opacity: 0.95;
}

/* ----------------------------------------------------
   REFLECTIVE MIND (Journal AI) CARD
---------------------------------------------------- */

.journal-ai-card {
  margin-top: 0.8rem;
  border-radius: 14px;
  padding: 0.9rem 1.1rem 0.95rem 1.1rem;
  background:
    radial-gradient(circle at 0% 0%, rgba(160,210,255,.14), transparent 55%),
    radial-gradient(circle at 100% 100%, rgba(120,255,200,.12), transparent 55%),
    #050810;
  border: 1px solid rgba(255,255,255,.18);
  box-shadow: 0 14px 34px rgba(0,0,0,.75);
  font-size: .93rem;
  color: #e8eef6;
}

.journal-ai-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: .75rem;
  margin-bottom: .4rem;
}

.journal-ai-pill {
  font-size: .72rem;
  text-transform: uppercase;
  letter-spacing: .16em;
  padding: .14rem .7rem;
  border-radius: 999px;
  border: 1px solid rgba(160,210,255,.85);
  background: rgba(8,16,32,.85);
  color: rgba(220,235,255,.96);
  white-space: nowrap;
}

.journal-ai-meta {
  font-size: .78rem;
  opacity: .8;
  text-align: right;
  white-space: nowrap;
}

.journal-ai-section {
  margin-top: .35rem;
}

.journal-ai-label {
  font-size: .78rem;
  text-transform: uppercase;
  letter-spacing: .14em;
  opacity: .78;
  margin-bottom: .1rem;
}

.journal-ai-section p {
  margin: 0;
  line-height: 1.5;
}

/* One-time pulse when a reflection was just saved */
.journal-ai-pulse {
  animation: journalPulse 0.85s ease-out 1;
  will-change: transform, box-shadow, opacity;
}

@keyframes journalPulse {
  0% {
    opacity: 0;
    transform: translateY(10px) scale(0.96);
    box-shadow: 0 0 0 0 rgba(160,210,255,0.0);
  }
  50% {
    opacity: 1;
    transform: translateY(-2px) scale(1.01);
    box-shadow: 0 0 32px 0 rgba(160,210,255,0.55);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
    box-shadow: 0 14px 34px rgba(0,0,0,.75);
  }
}
</style>
""", unsafe_allow_html=True)


def render_presence_banner():
    st.markdown("""
        <div class="presence-banner">
          <strong>Presence mode:</strong> Slow down for one minute. Breathe 4–2–6 and notice three simple sensations.
        </div>
    """, unsafe_allow_html=True)


def render_presence_micropractice():
    with st.expander("🧭 One-minute body scan (optional)"):
        a = st.checkbox("Feel the contact of your feet with the ground.")
        b = st.checkbox("Unclench jaw & soften shoulders.")
        c = st.checkbox("Notice one sound and one texture around you.")
        if st.button("Insert a Presence note into my reflection"):
            note = (
                "Presence note: feet grounded, jaw soft, shoulders relaxed; "
                "one sound, one texture."
            )
            prev = st.session_state.get("reflection_text", "")
            st.session_state["reflection_text"] = (
                prev + ("\n\n" if prev else "") + note
            ).strip()
            st.rerun()