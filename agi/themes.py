# agi/themes.py
from __future__ import annotations
from typing import Dict, Any

THEME_PROFILES: Dict[str, Dict[str, Any]] = {
    "Clarity":    {"persona":"Sees the essential truth beneath surface noise.",
                   "voice":"Grounded, simple, luminous.","max_words":80,
                   "mantra_hint":"Short, clear, present-tense."},
    "Compassion": {"persona":"Notices suffering and responds with tenderness.",
                   "voice":"Soft, kind, reassuring.","max_words":90,
                   "mantra_hint":"Heart-softening, present-tense."},
    "Courage":    {"persona":"Calls forth brave, truthful action without force.",
                   "voice":"Calm, steady, quietly bold.","max_words":90,
                   "mantra_hint":"Spine-straightening, present-tense."},
    "Presence":   {"persona":"Invites stillness, sensing, and immediacy.",
                   "voice":"Spacious, slow, attentive.","max_words":80,
                   "mantra_hint":"Breath-anchored, here-and-now."},
    "Surrender":  {"persona":"Releases control and rests in what is.",
                   "voice":"Gentle, yielding, devotional.","max_words":90,
                   "mantra_hint":"Open-handed, present-tense."},
    "Calm Sage":  {"persona":"Speaks in clean lines and small truths.",
                   "voice":"Minimal, measured, unhurried.","max_words":70,
                   "mantra_hint":"Smooth, balanced cadence."},
}

THEME_COLORS = {
    "Clarity":     ("#74EBD5", "#ACB6E5"),
    "Compassion":  ("#FBD3E9", "#BB377D"),
    "Courage":     ("#F7971E", "#FFD200"),
    "Presence":    ("#00C6FF", "#0072FF"),
    "Surrender":   ("#C9D6FF", "#E2E2E2"),
    "Calm Sage":   ("#A8E063", "#56AB2F"),
}
THEME_STYLES = {
    "Clarity":    {"bg":"linear-gradient(135deg,#c9f3ff,#b8e1ff,#cbd6ff)"},
    "Compassion": {"bg":"linear-gradient(135deg,#ffd6e6,#ffc6da,#ffd5ef)"},
    "Courage":    {"bg":"linear-gradient(135deg,#ffe1b3,#ffd39a,#ffe6c8)"},
    "Presence":   {"bg":"linear-gradient(135deg,#dcd7ff,#c9c0ff,#e4dbff)"},
    "Surrender":  {"bg":"linear-gradient(135deg,#d9ffe6,#c8f7dc,#e3ffef)"},
    "Calm Sage":  {"bg":"linear-gradient(135deg,#d8f1ff,#cfe8ff,#e1f4ff)"},
}

def theme_gradient(theme: str) -> tuple[str,str]:
    return THEME_COLORS.get(theme, ("#2b5876","#4e4376"))