# agi/questions.py
from __future__ import annotations
import datetime, random
import streamlit as st

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

def get_guided_questions(theme: str, prompt_id: str, k: int = 3):
    pool = GUIDED_QUESTIONS.get(theme, [])
    if not pool: return []
    today = datetime.date.today().isoformat()
    key = f"guided_q::{prompt_id}::{today}"
    if key in st.session_state:
        return st.session_state[key]
    rnd = random.Random(hash((prompt_id, today)))
    selected = rnd.sample(pool, k=min(k, len(pool)))
    st.session_state[key] = selected
    return selected

def shuffle_guided_questions(prompt_id: str):
    today = datetime.date.today().isoformat()
    for k in list(st.session_state.keys()):
        if k.startswith(f"guided_q::{prompt_id}::{today}"):
            del st.session_state[k]