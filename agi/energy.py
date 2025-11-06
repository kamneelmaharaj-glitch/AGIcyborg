# agi/energy.py
from __future__ import annotations
import math

POS_WORDS = {"calm","clear","grateful","light","open","strong","peace","centered","present","focus","soft","love"}
NEG_WORDS = {"tired","angry","sad","foggy","heavy","fear","anxious","overwhelmed","stuck","doubt"}

MOOD_TO_ENERGY = {
    "low":   -0.35,
    "steady": 0.0,
    "open":   0.25,
    "bright": 0.5,
}

def _word_boost(text: str) -> float:
    if not text: return 0.0
    t = text.lower()
    pos = sum(w in t for w in POS_WORDS)
    neg = sum(w in t for w in NEG_WORDS)
    score = (pos - neg) / 6.0
    return max(-0.6, min(0.6, score))

def compute_energy_score(mood: str | None, reflection_text: str) -> float:
    base = MOOD_TO_ENERGY.get((mood or "").strip().lower(), 0.0)
    lift = _word_boost(reflection_text or "")
    score = max(-1.0, min(1.0, base + lift))
    return round(score, 3)

def compute_presence_score(stillness_note: str | None) -> float:
    if not stillness_note: return 0.15
    length = len(stillness_note.strip())
    val = 0.2 + min(0.8, math.log10(1 + length) / 1.2)
    return round(max(0.0, min(1.0, val)), 3)