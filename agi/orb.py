# agi/orb.py
from __future__ import annotations
import streamlit as st

def render_breath_orb(avg_energy: float | None, avg_presence: float | None, size: int = 120):
    """
    A soft, breathing orb. Speed/intensity scales with energy; glow with presence.
    - avg_energy in [-1, +1] (we map to speed)
    - avg_presence in [0, 1]  (we map to glow)
    """
    e = float(avg_energy or 0.0)
    p = float(avg_presence or 0.0)

    # Map energy -> breathing duration (calmer = slower)
    # abs(e)=0.0 -> 8.0s, abs(e)=1.0 -> 3.0s
    duration = 8.0 - 5.0 * min(abs(e), 1.0)

    # Map presence -> glow intensity (0 -> 0.25, 1 -> 0.9)
    glow = 0.25 + 0.65 * max(min(p, 1.0), 0.0)

    # Subtle hue shift: negative energy → cooler; positive → warmer
    # e in [-1,1] => hue in [190, 160]
    hue = 175 - 15 * e

    html = f"""
    <div class="orb-wrap">
      <div class="orb"></div>
    </div>
    <style>
      .orb-wrap {{
        display:flex; align-items:center; justify-content:center;
        width:{size}px; height:{size}px;
      }}
      .orb {{
        width:{size*0.9}px; height:{size*0.9}px;
        border-radius:50%;
        background: radial-gradient(
          circle at 35% 30%,
          hsl({hue}deg 80% 65% / {glow}) 0%,
          hsl({hue}deg 80% 45% / {glow*0.6}) 35%,
          hsl({hue}deg 75% 25% / {glow*0.3}) 70%,
          transparent 100%
        );
        box-shadow:
          0 0 12px hsl({hue}deg 80% 60% / {glow*0.8}),
          inset 0 0 18px hsl({hue}deg 90% 70% / {glow*0.7});
        animation: breathe {duration:.2f}s ease-in-out infinite;
        filter: blur(0.2px);
      }}
      @keyframes breathe {{
        0%   {{ transform: scale(0.95); filter: brightness(0.98);}}
        50%  {{ transform: scale(1.04); filter: brightness(1.03);}}
        100% {{ transform: scale(0.95); filter: brightness(0.98);}}
      }}
    </style>
    """
    st.markdown(html, unsafe_allow_html=True)