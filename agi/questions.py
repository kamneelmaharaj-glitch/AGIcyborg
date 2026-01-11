# agi/questions.py
from __future__ import annotations

import random
from typing import List, Dict, Optional

import streamlit as st

# ------------------------------------------------------------
# 1) Theme-based guided question bank
# ------------------------------------------------------------

# Normalized theme name → list of questions
# (You can tweak / expand these any time.)
THEME_QUESTIONS: Dict[str, List[str]] = {
    "clarity": [
        "What truth is asking to be seen today?",
        "If all distractions fell silent, what would you realize?",
        "What feels foggy, and what might bring light to it?",
        "What one small step could bring more clarity to this?",
        "What am I pretending not to know about this situation?",
        "If this were simple, what would I see or do next?",
        "What story am I telling myself that might not be fully true?",
        "What question, if answered, would change everything for me right now?",
    ],
    "courage": [
        "Where is fear gently asking me to grow?",
        "What am I avoiding that I know would set me free?",
        "What would I do here if I trusted my own strength?",
        "What small brave action could I take in the next 24 hours?",
        "If I were not afraid of failing, what would I try?",
        "What part of me wants to speak but feels unsafe to be heard?",
        "How might I move with fear instead of waiting for it to vanish?",
    ],
    "compassion": [
        "Where in my life is kindness needed most right now?",
        "If I could see myself as a dear friend, what would I say to me?",
        "What weight am I carrying that I have never fully named?",
        "What would it look like to soften, just 5% more, around this?",
        "Who might need a gentle check-in from me this week?",
        "What is one way I can honour my limits with tenderness?",
        "Where have I grown this year that deserves quiet appreciation?",
    ],
    "presence": [
        "What is actually happening in this moment, beneath the thoughts?",
        "What body sensations are here if I pause for three breaths?",
        "Where is my attention pulled right now, and why?",
        "What would it feel like to do this next action 20% slower?",
        "What tiny ritual could help me arrive fully to my day?",
        "If I listened deeply, what is my body trying to tell me?",
    ],
    "surrender": [
        "What am I gripping that is asking to be released?",
        "Where might life be wiser than my current plan?",
        "What would trusting the process look like in this situation?",
        "What is outside my control that I can bless and let be?",
        "If I laid this at the feet of the Divine, what would shift in me?",
    ],
    "calm sage": [
        "If a wise, calm version of me spoke, what would they say?",
        "What lesson might be quietly forming beneath this challenge?",
        "Where in my life am I invited to respond, not react?",
        "What could I simplify or gently say no to this week?",
        "What long-term value do I want to protect with today’s choices?",
    ],
    # Fallback bucket for any other / unknown themes
    "reflection": [
        "What feels most alive in me today?",
        "What am I grateful for that I rarely mention?",
        "What did today reveal about what matters to me?",
        "Where did I feel most like myself recently?",
        "What is one small way I can honour my values tomorrow?",
    ],
}

# Generic cross-theme prompts that can be blended into any theme
GENERIC_QUESTIONS: List[str] = [
    "What truth is asking to be seen today?",
    "What feels heavy, and what might make it 1% lighter?",
    "What would my future self thank me for doing today?",
    "What needs to be said, even if only on this page?",
    "What wants to begin, and what wants to end?",
]
# Short explanatory blurbs per theme for the Guided Questions header
THEME_BLURBS: Dict[str, str] = {
    "clarity": (
        "Questions to help you see what is actually true, beneath distraction "
        "and mental fog."
    ),
    "courage": (
        "Questions to help you move with fear and take one small, honest step "
        "in the direction of your growth."
    ),
    "compassion": (
        "Questions to soften self-judgment, honour your limits, and meet yourself "
        "and others with kindness."
    ),
    "presence": (
        "Questions to bring you back into your body, this breath, and the reality "
        "of this moment."
    ),
    "surrender": (
        "Questions to loosen your grip, trust the process, and hand what you can’t "
        "control back to Life."
    ),
    "calm sage": (
        "Questions to listen for the calm, wise voice inside you and respond from "
        "steadiness rather than reactivity."
    ),
    # Fallback / general reflection
    "reflection": (
        "Gentle prompts for honest self-reflection so you can see your life a little "
        "more clearly today."
    ),
}

def _normalize_theme(theme: Optional[str]) -> str:
    if not theme:
        return "reflection"
    t = str(theme).strip().lower()
    # Simple normalization hooks if you ever rename themes
    if "clarity" in t:
        return "clarity"
    if "courage" in t:
        return "courage"
    if "compassion" in t:
        return "compassion"
    if "presence" in t:
        return "presence"
    if "surrender" in t:
        return "surrender"
    if "calm" in t or "sage" in t:
        return "calm sage"
    return "reflection"

def get_theme_blurb(theme: Optional[str]) -> str:
    """Return a short, theme-specific description for the Guided Questions header."""
    t = _normalize_theme(theme)
    return THEME_BLURBS.get(t, THEME_BLURBS["reflection"])
# ------------------------------------------------------------
# 2) Public API used by app.py
# ------------------------------------------------------------

def get_guided_questions(
    theme: Optional[str],
    prompt_id: str,
    k: int = 3,
) -> List[str]:
    """
    Return up to k guided questions for the given theme + prompt.

    - Theme determines the question bank.
    - Questions are cached per-prompt in st.session_state so they stay
      stable across reruns until the user taps Shuffle.
    """
    cache_key = f"gq_cache::{prompt_id}"

    # Build cache once per prompt
    if cache_key not in st.session_state:
        t_key = _normalize_theme(theme)
        theme_qs = THEME_QUESTIONS.get(t_key, THEME_QUESTIONS["reflection"])

        # Blend in generic questions without duplicates
        blended = list(theme_qs)
        for q in GENERIC_QUESTIONS:
            if q not in blended:
                blended.append(q)

        # Initial order: deterministic but slightly varied
        # so prompts don't feel fixed like a form.
        random.seed(hash(prompt_id) % (2**32))
        random.shuffle(blended)

        st.session_state[cache_key] = blended

    qs: List[str] = st.session_state.get(cache_key, [])
    return qs[:k]


def shuffle_guided_questions(prompt_id: str) -> None:
    """
    Shuffle the cached questions for this prompt.

    Only reorders the in-memory list; the 'used' tracking and
    reflection text are handled in app.py.
    """
    cache_key = f"gq_cache::{prompt_id}"
    qs = st.session_state.get(cache_key)
    if not qs:
        return
    random.shuffle(qs)
    st.session_state[cache_key] = qs