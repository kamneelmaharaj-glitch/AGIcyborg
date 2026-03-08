# agi/deepen_ai.py

# ============================================================
# C4 — INSIGHT VOICE INTEGRITY (SEALED)
#
# Guarantees:
# - No directives
# - No coaching
# - No correction
# - No causality dependency
# - Stable under fallback and rate limits
#
# AI availability MUST NOT affect voice correctness.
#
# Sealed: <today’s date>
# ============================================================

from __future__ import annotations

import hashlib
from typing import List, Tuple, Optional, Dict, Any


from agi.mood import detect_mood
from agi.rhythm import infer_response_mode
from agi.dharma import infer_practice_phase, preferred_microstep_category

import streamlit as st
import os
import re
from agi.silence_contract import should_silence
from agi.utils import resolve_microstep_source, resolve_microstep_dominance

from agi.memory import record_reflection_memory

from agi.threads.presence_thread import (
    infer_presence_stage,
    update_presence_stage as presence_update_stage,
    presence_stage_label,
)


TEST_MODE = os.getenv("DEEPEN_TEST_MODE") == "1"


def _attach_presence_debug(
    *,
    dbg: dict,
    reflection_text: str,
    mood: str,
    silenced: bool,
    silence_reason: str | None,
    presence_stage_prev: int = 0,
    presence_drift_hits_prev: int = 0,
) -> None:

    stage_today, stage_reason = infer_presence_stage(
        reflection_text=reflection_text,
        mood=mood,
        silenced=silenced,
    )

# -----------------------------------
# Silence output (C5)
# -----------------------------------
def _silence_output(*, mood: str) -> tuple[str, str | None, str]:
    """
    C5 Silence Output Contract

    - Stillness is allowed
    - Insight MUST be None
    - Microstep must be grounding, not directional
    """

    if mood in ("overwhelmed", "heavy"):
        stillness = "This moment is being held."
        microstep = "Place one hand on your chest."
    elif mood in ("drained", "tender"):
        stillness = "You are already here."
        microstep = "Place one hand on your chest."
    else:
        stillness = "Nothing is missing here."
        microstep = "Sit upright for ten seconds."

    return stillness, None, microstep

# ---------------------------------------------------------------------------
# Debug state for Deepen (A.4)
# ---------------------------------------------------------------------------

_last_debug: Dict[str, Any] = {}


def get_last_deepen_debug() -> Dict[str, Any]:
    """Return a copy of the last Deepen generation metadata."""
    return dict(_last_debug)


# -------------------------------------------------------------------
# System primer (shared across all themes)
# -------------------------------------------------------------------

SYSTEM_PRIMER = (
    "You are AGIcyborg's Deepen Mentor.\n"
    "- Voice: warm, grounded, and concise.\n"
    "- INSIGHT: 1 sentence, 8–22 words, ends with punctuation.\n"
    "- No directives ('you should/must/need to'), no therapy/diagnosis, no cosmic certainty.\n"
    "- Address the user naturally (you may use 'you', but never in a commanding tone).\n"
    "- MICROSTEP: one single concrete action under 2 minutes, today.\n"
    "- No lists, no multi-step sequences, no questions, no vague advice.\n"
)

def _select_microstep_category(theme: str, tail_line: str) -> str:
    """
    Deterministically select a microstep category.

    Priority:
      1) Semantic match from tail_line (if clear)
      2) Deterministic hash fallback (stable across runs)
    """

    tl = (tail_line or "").strip().lower()

    # --- 1) Semantic fast-path (cheap, deterministic) ---
    for cat in MICROSTEP_CATEGORIES:
        if _matches_category(tl, cat):
            return cat

    # --- 2) Deterministic fallback ---
    seed = f"{theme}:{tail_line}".encode("utf-8")
    n = int(hashlib.sha256(seed).hexdigest(), 16)
    idx = n % len(MICROSTEP_CATEGORIES)
    return MICROSTEP_CATEGORIES[idx]

def _select_stillness_note(theme: str, tail_line: str) -> str:
    theme_pool = STILLNESS_NOTES.get(theme, [])
    pool = theme_pool if theme_pool else STILLNESS_NOTES.get("universal", [])
    if not pool:
        return "Nothing is missing here."

    seed = f"stillness:{theme}:{tail_line}".encode("utf-8")
    n = int(hashlib.sha256(seed).hexdigest(), 16)
    return pool[n % len(pool)]

_MOOD_CATEGORY_BIAS = {
    "overwhelmed": "pacing",
    "drained": "posture",     # “supported + upright”
    "heavy": "touch",
    "tender": "touch",
    "soft": "breath",
    "clear": "posture",
    "focused": "environment",
}

def _apply_mood_category_bias(chosen_category: str, mood: str, norm_text: str = "") -> str:
    mood = (mood or "").strip().lower()
    if not mood:
        return chosen_category

    biased = _MOOD_CATEGORY_BIAS.get(mood)
    if not biased or biased == chosen_category:
        return chosen_category

    if mood == "focused" and biased == "environment":
        t = (norm_text or "").lower()
        if not any(w in t for w in ("desk", "workspace", "screen", "clutter", "setup", "station")):
            return chosen_category

    return biased



_BANNED_INSIGHT_PHRASES = (
    "everything happens for a reason",
    "just breathe",
    "you got this",
    "don't worry",
)

_DIAGNOSIS_WORDS = (
    "anxiety", "depression", "adhd", "ptsd", "panic", "trauma", "disorder",
)

_HARD_DIRECTIVES = (
    "you should", "you must", "you need to", "do this", "stop", "never",
)

_ADVICE_VERBS = (
    "do ", "fix ", "change ", "stop ",
    "start ", "try ", "remember ",
    "focus ", "let go", "practice "
)
def _contains_advice_language(t: str) -> bool:
    low = t.lower()
    return any(v in low for v in _ADVICE_VERBS)

def _strip_advice_language(t: str) -> str:
    """
    Removes direct advice framing from insight text.
    Converts 'you should/need to/try to' patterns into witnessing language.
    """
    s = (t or "").strip()
    if not s:
        return s

    low = s.lower()
    starters = (
        "you should ",
        "you must ",
        "you need to ",
        "try to ",
        "remember to ",
        "make sure ",
    )
    if any(low.startswith(x) for x in starters):
        return _rewrite_as_observation(s)

    # remove mid-sentence coaching phrases
    for phrase in ("this will help", "so that you can", "in order to", "which will allow"):
        if phrase in low:
            s = re.sub(re.escape(phrase), "", s, flags=re.IGNORECASE)

    return re.sub(r"\s+", " ", s).strip()

def _sounds_action_dependent(t: str) -> bool:
    low = t.lower()
    return any(x in low for x in (
        "so that you can",
        "this will help you",
        "in order to",
        "which will allow",
    ))

def _rewrite_as_observation(t: str) -> str:
    # blunt but safe fallback
    return "There is something here that is already being noticed."

def _rewrite_as_witnessing(t: str) -> str:
    """
    Convert coaching/causal phrasing into witnessing.
    Keep it short; do not introduce directives.
    """
    s = (t or "").strip()
    low = s.lower()

    # Remove explicit coaching / causality
    for m in _INSIGHT_COACHING_MARKERS:
        if m in low:
            idx = low.find(m)
            s = s[:idx].rstrip(" ,;:-")
            break

    # If we cut too hard, return a neutral witness
    if len(s) < 12:
        return "What you feel is already being noticed."

    if s and s[-1] not in ".!?":
        s += "."
    return s

def _limit_sentences(text: str, max_sentences: int = 2) -> str:
    t = (text or "").strip()
    if not t:
        return t
    # split on sentence enders
    parts = re.split(r'(?<=[.!?])\s+', t)
    parts = [p.strip() for p in parts if p.strip()]
    return " ".join(parts[:max_sentences]).strip()

def _normalize_step(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def _avoid_repeat_microstep(
    microstep: str,
    chosen_category: str,
    recent_followups: List[str],
    window: int = 3,
) -> Tuple[str, bool, Dict[str, object]]:
    """
    Deterministic anti-repeat:
    - If the microstep matches any of the last N microsteps, rotate via category pool.
    Returns: (final_step, reused, meta)
    """
    meta: Dict[str, object] = {
        "repeat_hit": False,
        "repeat_action": "",
        "repeat_match": "",
        "window": window,
        "category": chosen_category,
    }

    recent_steps = _recent_microsteps(recent_followups, window=window)
    if not recent_steps:
        return microstep, False, meta

    norm = _normalize_step(microstep)

    for s in recent_steps:
        if _normalize_step(s) == norm:
            meta["repeat_hit"] = True
            meta["repeat_match"] = (s or "").strip()

            rotated, _cycle_meta = _cycle_fallback_for_category(
                category=chosen_category,
                exclude=microstep,
                recent_followups=recent_followups,
                window=window,
            )

            meta["repeat_action"] = "rotated"
            return rotated, True, meta

    return microstep, False, meta
    
def _soften_directives(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return t

    low = t.lower()
    # soften common directive phrases
    repl = {
        "you should": "you can",
        "you must": "you may",
        "you need to": "it may help to",
        "try to": "you can try to",
    }
    for a, b in repl.items():
        if a in low:
            # case-insensitive replace
            t = re.sub(re.escape(a), b, t, flags=re.IGNORECASE)
    return t.strip()

def _remove_cliches_and_diagnosis(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return t

    low = t.lower()

    for p in _BANNED_INSIGHT_PHRASES:
        if p in low:
            # remove the whole sentence containing it
            t = re.sub(r'[^.!?]*' + re.escape(p) + r'[^.!?]*[.!?]?\s*', '', t, flags=re.IGNORECASE)

    # Remove clinical diagnosis words if they appear
    for w in _DIAGNOSIS_WORDS:
        if w in t.lower():
            t = re.sub(r'\b' + re.escape(w) + r'\b', "stress", t, flags=re.IGNORECASE)

    return t.strip()

def _count_sentences_simple(text: str) -> int:
    parts = re.split(r"[.!?]+", (text or "").strip())
    return sum(1 for p in parts if p.strip())

def _ensure_gentle_dharma_voice(theme_label: str, mood: str, text: str) -> str:
    t = (text or "").strip()
    if not t:
        return t

    low = t.lower()

    # de-spiritualize if needed (keep)
    abstract_markers = ("the universe", "destiny", "cosmic", "divine plan")
    if any(m in low for m in abstract_markers):
        t = re.sub(r"\b(universe|destiny|cosmic|divine plan)\b", "life", t, flags=re.IGNORECASE)
        low = t.lower()

    # turn "theme hint" into a MICRO-SECOND SENTENCE (not a suffix clause)
    theme_sentence = {
        "Devotion": "This can be an offering.",
        "Surrender": "No forcing is needed.",
        "Courage": "A small step is enough.",
        "Compassion": "Gentleness is allowed.",
        "Discipline": "Steadiness is enough.",
        "Presence": "What can be felt is here.",
        "Clarity": "Simplicity is available.",
        "Balance": "A sustainable pace is possible.",
    }.get(theme_label, "")

    if not theme_sentence:
        return t

    # --- Skip if already carries the theme signal (your markers, kept) ---
    equivalent_markers = {
        "Presence": ("present moment", "right now", "here and now", "in this moment", "what you can feel"),
        "Clarity": ("simple", "simplicity", "clear", "clarity", "name it"),
        "Compassion": ("gentle", "soft", "tender", "kind", "care"),
        "Discipline": ("steady", "steadiness", "consistent", "repeatable"),
        "Balance": ("sustainable", "not rushing", "pace", "rhythm"),
        "Surrender": ("release", "allow", "let go", "no forcing"),
        "Courage": ("one small", "tiny step", "small step"),
        "Devotion": ("offering", "service", "devotion"),
    }
    for marker in equivalent_markers.get(theme_label, ()):
        if marker in low:
            return t

    # --- Make it rare: only add when short and not already 2 sentences ---
    if len(t) >= 110:
        return t

    # if already 2 sentences, don't add another
    if _count_sentences_simple(t) >= 2:
        return t

    # if ends with ? or !, don't append (tone)
    if t.endswith(("?", "!")):
        return t

    # Append as second sentence (clean, no comma-qualifier)
    if t[-1] not in ".!?":
        t = t + "."

    return (t + " " + theme_sentence).strip()

def _dedupe_tone_echoes(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return t

    # Collapse duplicated "in this moment" patterns
    t = re.sub(r"(in this moment)(,\s*\1)+", r"\1", t, flags=re.IGNORECASE)
    t = re.sub(r"(right now)(,\s*\1)+", r"\1", t, flags=re.IGNORECASE)

    # If "present moment" already appears, drop trailing ", in this moment"
    t = re.sub(r"(present moment)\s*,\s*in this moment\b", r"\1", t, flags=re.IGNORECASE)

    # If sentence already contains "moment", avoid ending with ", in this moment"
    t = re.sub(r"(moment[^.]*),\s*in this moment\b", r"\1", t, flags=re.IGNORECASE)

    # Remove doubled qualifiers like ", with simplicity, with simplicity."
    t = re.sub(r",\s*(with|without|in)\s+([a-z\s]+?)\s*,\s*\1\s+\2\b",
               r", \1 \2", t, flags=re.IGNORECASE)

    return t.strip()

def _dedupe_insight_echoes(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return t

    low = t.lower()

    # 1) Don't allow "present moment, in this moment"
    t = re.sub(r"(present moment)\s*,\s*(in this moment)\b", r"\1", t, flags=re.IGNORECASE)

    # 2) Don't repeat "in this moment" more than once
    if low.count("in this moment") > 1:
        parts = re.split(r"(\bin this moment\b)", t, flags=re.IGNORECASE)
        out = []
        seen = 0
        for p in parts:
            if re.fullmatch(r"\bin this moment\b", p, flags=re.IGNORECASE):
                seen += 1
                if seen > 1:
                    continue
            out.append(p)
        t = "".join(out)

    # 3) Collapse duplicated trailing qualifiers like ", with simplicity, with simplicity."
    t = re.sub(
        r",\s*(with|without|in)\s+([a-z\s]+?)\s*,\s*\1\s+\2\b",
        r", \1 \2",
        t,
        flags=re.IGNORECASE,
    )

    # 4) Remove accidental double punctuation
    t = re.sub(r"\s+([,.!?])", r"\1", t)
    t = re.sub(r"([,.!?]){2,}", r"\1", t)

    return t.strip()

def _vary_common_insight_phrases(theme_label: str, mood: str, text: str) -> str:
    t = (text or "").strip()
    if not t:
        return t

    key = (theme_label + "|" + mood).lower()
    idx = sum(ord(c) for c in key) % 3

    variants = [
        # idx 0
        (r"^Slowing down (allows|invites) you to\b", "A softer pace is here; you can"),
        (r"^Your body is (asking|signaling|nudging|pointing)\b.*?\bto\b", "Your body is calling you back to"),
        (r"^You are learning to\b", "This is practice in learning to"),

        # idx 1
        (r"^Slowing down (allows|invites) you to\b", "There is room to slow down; you can"),
        (r"^Your body is (asking|signaling|nudging|pointing)\b.*?\bto\b", "Your body is returning you to"),
        (r"^You are learning to\b", "A steady rhythm is forming as you learn to"),

        # idx 2
        (r"^Slowing down (allows|invites) you to\b", "A small pause is already here; you can"),
        (r"^Your body is (asking|signaling|nudging|pointing)\b.*?\bto\b", "Your body is inviting you to"),
        (r"^You are learning to\b", "You are practicing how to"),
    ]

    start = idx * 3
    for pat, repl in variants[start:start + 3]:
        if re.search(pat, t, flags=re.IGNORECASE):
            t = re.sub(pat, repl, t, flags=re.IGNORECASE)
            break

    return t.strip()

# Insight-level "coaching causality" markers
_INSIGHT_COACHING_MARKERS = (
    "so that you can",
    "so you can",
    "in order to",
    "which will allow",
    "this will help",
    "this helps you",
    "then you can",
    "then you will",
    "if you just",
    "start by",
    "try to",
    "remember to",
    "make sure",
)

def _insight_sounds_coaching(t: str) -> bool:
    low = (t or "").lower()
    return any(m in low for m in _INSIGHT_COACHING_MARKERS)

"""
AGIcyborg Insight Voice Contract

Insights must:
- Reflect, not instruct
- Speak beside the user, not above them
- Avoid advice, reassurance, or outcome promises
- Stay grounded in present-moment experience
- Use at most two sentences
- Feel like quiet companionship, not guidance

If an insight pushes, fixes, reassures, or explains — it is wrong.
"""
def _align_insight_tone(theme_label: str, mood: str, insight: str) -> str:
    t = (insight or "").strip()
    if not t:
        return t

    t = _remove_cliches_and_diagnosis(t)
    t = _soften_directives(t)

    if _contains_advice_language(t):
        t = _strip_advice_language(t)

    t = _limit_sentences(t, 2)

    low = t.lower()
    if any(low.startswith(x) for x in (
        "you should", "you must", "you need to", "try to", "remember to", "make sure",
    )):
        t = _rewrite_as_observation(t)

    if _sounds_action_dependent(t) or _insight_sounds_coaching(t):
        t = _rewrite_as_witnessing(t)
        t = _ensure_gentle_dharma_voice(theme_label, mood, t)
        t = _dedupe_insight_echoes(t)

    # first pass (as you already have)
    t = _remove_stale_openers(theme_label, mood, t)

    # final normalize
    t = re.sub(r"\s+", " ", t).strip()

    # FINAL hard-guard (catches reintroduced stale openers)
    t = _remove_stale_openers(theme_label, mood, t)

    return t

_STALE_OPENERS = (
    "slowing down allows you to",
    "slowing down invites you to",
    "your body is asking you to",
    "your body is signaling",
    "your body is nudging",
    "your body is inviting you to",     # if you want this banned too
    "your body is calling you back to", # if you want this banned too
    "you are learning to keep",
)

def _remove_stale_openers(theme_label: str, mood: str, text: str) -> str:
    t = (text or "").strip()
    if not t:
        return t

    low = t.lower().strip()

    if any(low.startswith(s) for s in _STALE_OPENERS):
        t2 = _vary_common_insight_phrases(theme_label, mood, t).strip()
        low2 = t2.lower().strip()

        if any(low2.startswith(s) for s in _STALE_OPENERS) or _insight_sounds_coaching(t2):
            t2 = _rewrite_as_witnessing(t).strip()
            low2 = t2.lower().strip()

        # LAST resort: guaranteed non-stale, witnessing
        if any(low2.startswith(s) for s in _STALE_OPENERS):
            t2 = "Something in you is returning to what can be felt, right now."

        return t2.strip()

    return t
# -------------------------------------------------------------------
# Theme tones (prompt-only nudges)
# -------------------------------------------------------------------

THEME_TONES: Dict[str, str] = {
    "Presence": (
        "Tone: slow, spacious, and body-aware. "
        "Invite me back to breath, sensation, and this exact moment."
    ),
    "Clarity": (
        "Tone: clear, honest, and gently direct. "
        "Focus on seeing what is true and naming it with kindness."
    ),
    "Courage": (
        "Tone: encouraging and steady. "
        "Acknowledge fear but emphasize one small brave step."
    ),
    "Compassion": (
        "Tone: warm, non-judgmental, and soft. "
        "Emphasize self-kindness and understanding."
    ),
    "Balance": (
        "Tone: pacing, gentle, and wise. "
        "Help me place effort where it matters and honour rest."
    ),
    "Discipline": (
        "Tone: simple, structured, and consistent. "
        "Focus on one clear, repeatable action — never harsh."
    ),
    "Purpose": (
        "Tone: mythic but grounded. "
        "Connect today’s step to a longer calling without pressure."
    ),
    "Devotion": (
        "Tone: soft, sincere, quietly surrendered; focused on offering and humility; "
        "universal and non-denominational."
    ),
    "Surrender": (
        "Tone: trusting and gentle. "
        "Help me release what I cannot control and rest into support."
    ),
    "Calm-Sage": (
        "Tone: calm, elder-like, and humble. "
        "Offer perspective from a quiet inner wisdom."
    ),
}

THEME_SIGNATURES = {
    # Presence = embodiment + immediacy (non-productivity)
    "Presence": {
        # existing
        "body", "breath", "present", "moment", "here",
        "feel", "notice", "ground", "sensation",
        "slow", "slowing", "pause", "aware", "awareness",

    # witnessing additions (non-directive, non-stale)
            "felt",
            "can be felt",
            "right now",
            "returning",
            "arriving",
            "already here",
    },

    # Clarity = simplicity + truth without force
    "Clarity": {
        "clarity", "clear", "simple", "simplicity",
        "true", "truth", "name", "naming", "see", "quiet"
    },

    # Discipline = repeatability + steadiness (not grind)
    "Discipline": {
        "steady", "steadiness", "repeat", "repeatable",
        "small", "consistency", "momentum", "practice"
    },

    # Compassion = gentleness toward self
    "Compassion": {
        "gentle", "gentleness", "soft", "softness",
        "kind", "care", "tender", "warm"
    },

    # Balance = sustainable pacing
    "Balance": {
        "balance", "sustainable", "rhythm",
        "pace", "space", "ease", "supported"
    },

    # Purpose = meaning without destiny language
    "Purpose": {
        "purpose", "meaning", "matters",
        "values", "direction", "important", "call"
    },

    # Optional future themes (safe to keep, not enforced)
    "Courage": {
        "brave", "honest", "edge", "face", "stand"
    },

    "Surrender": {
        "release", "allow", "ease", "let go", "without forcing"
    },

    "Devotion": {
        "offering", "service", "sincerity", "care", "commitment"
    },
}
# Theme signatures are diagnostic only.
# They must NEVER alter the insight text.
def _theme_signature_strength(theme_label: str, insight: str) -> tuple[str, int]:
    """
    Debug-only. Returns (strength, matches_count).
    strength: none | weak | ok
    """
    words = THEME_SIGNATURES.get(theme_label)
    if not words:
        return ("ok", 0)  # theme not tracked -> do not penalize

    t = (insight or "").lower()
    hits = sum(1 for w in words if w in t)

    if hits <= 0:
        return ("none", hits)
    if hits == 1:
        return ("weak", hits)
    return ("ok", hits)


# -------------------------------------------------------------------
# Stillness Notes (Journal Intelligence v2.1 — deterministic)
# -------------------------------------------------------------------

STILLNESS_NOTES = {
    "universal": [
        "Nothing is missing here.",
        "The moment is your teacher.",
        "You are already here.",
    ],
    "Clarity": [
        "The truth only required stillness to be seen.",
        "Clarity arrives when the mind is calm.",
        "Clarity can return without force..",
    ],
    "Devotion": [
        "An honest effort carries weight.",
        "Service is not only external.",
    ],
}

# -------------------------------------------------------------------
# Microstep categories (A.8)
# -------------------------------------------------------------------

MICROSTEP_CATEGORIES = [
    "breath",
    "touch",
    "posture",
    "pacing",
    "environment",
]

MICROSTEP_HINTS: Dict[str, str] = {
    "breath": (
        "Use one breath-adjacent action WITHOUT 'inhale/exhale' pairs and do NOT start with 'Breathe'. "
        "Prefer verbs like Pause, Notice, Count, Whisper."
    ),
    "posture": "Use one small change in posture or body position (one action only).",
    "environment": "Use one gentle change in your immediate surroundings (move/clear/set a single item).",
    "pacing": (
        "Use one pacing action only (Pause / Slow / Wait). "
        "Do NOT add noticing, reflecting, or a second instruction."
    ),
    "touch": "Use one grounding physical touch as the action (one action only).",
}

ALLOWED_MICROSTEP_VERBS = (
    "take", "place", "sit", "stand", "walk", "write", "touch",
    "look", "name", "put", "move", "clear", "stretch", "open", "close",
    "hold", "drink", "wash", "step", "pause", "turn",
    "set", "rest", "notice", "rearrange",
)

# NOTE: You explicitly do NOT want microsteps starting with "Breathe".
# We keep "breathe" OUT of the allowed verbs list on purpose.



def _extract_tail_line(reflection_text: str) -> str:
    body = (reflection_text or "").strip()
    if not body:
        return "—"
    parts = [p.strip() for p in body.split("\n") if p.strip()]
    return parts[-1] if parts else "—"


# -------------------------------------------------------------------
# Deterministic fallbacks (single-action ONLY; no "and")
# -------------------------------------------------------------------

THEME_FALLBACK_MICROSTEP: Dict[str, str] = {
    "Presence":   "Place one hand on your abdomen.",
    "Clarity":    "Write one honest sentence about what is most true right now.",
    "Courage":    "Send one short message you have been avoiding.",
    "Compassion": "Place one hand on your chest.",
    "Purpose":    "Write one sentence naming what matters most today.",
    "Balance":    "Pause for ten seconds before your next task.",
    "Discipline": "Clear one small space in front of you.",
    "Devotion":   "Place your palms together for ten seconds as a quiet offering.",
    "Surrender":  "Write one line naming what you cannot control today.",
    "Calm-Sage":  "Sit upright for ten seconds.",
}

THEME_FALLBACK_INSIGHT: Dict[str, str] = {
    "Presence":   "Something in you is returning to what can be felt, right now.",
    "Clarity":    "What feels true is already close, even if it has not been named yet.",
    "Courage":    "A small honest edge is here, and it does not need force.",
    "Compassion": "Softness is allowed here, even with what feels hard to hold.",
    "Purpose":    "What matters is quietly present, even if the path is not fully clear.",
    "Balance":    "A steadier rhythm is possible without pushing against yourself.",
    "Discipline": "Small repeatable steps are here, without pressure or performance.",
    "Devotion":   "This effort can be held as an offering, without making it heavy.",
    "Surrender":  "Some things can rest where they are, without being solved tonight.",
    "Calm-Sage":  "A quiet knowing is present, even beneath the noise.",
}

# -------------------------------------------------------------------
# Guardrails
# -------------------------------------------------------------------

def _is_valid_microstep(step: str) -> bool:
    if not step:
        return False

    s = step.strip().lower()

    # Must start with a physical/behavior verb
    if not any(s.startswith(v + " ") or s == v for v in ALLOWED_MICROSTEP_VERBS):
        return False

    # Length sanity
    if len(s) > 240:
        return False

    return True


def _is_mantra_like(step: str) -> bool:
    t = (step or "").strip().lower()
    if not t:
        return True

    # Strong mantra / affirmation patterns
    if "breathe in" in t and "breathe out" in t:
        return True
    if "inhale" in t and "exhale" in t:
        return True
    if t.startswith("i "):  # "I am..." affirmations
        return True

    # Explicit preference: do not start with "breathe"
    if t.startswith("breathe "):
        return True

    # Soft coaching / mantra-ish fragments
    forbidden = (
        "remember", "allow yourself", "be present", "stay with",
        "return to", "notice that", "you are", "trust that",
        "let yourself", "feel into", "hold the feeling",
    )
    if any(frag in t for frag in forbidden):
        return True

    return False


def _looks_multi_step(step: str) -> bool:
    t = (step or "").strip().lower()
    if " and " in t:
        return True
    if ";" in t or " then " in t or " after " in t:
        return True
    if "," in t:
        # commas often hide multi-step sequences
        return True
    return False


def _starts_with_allowed_verb_titlecase(step: str) -> bool:
    s = (step or "").strip()
    allowed = (
    "Take", "Place", "Sit", "Stand", "Look", "Name",
    "Notice", "Set", "Walk", "Turn", "Write", "Hold", "Rest",
    "Put", "Move", "Clear", "Open", "Close", "Pause", "Step",
    "Touch", "Drink", "Wash", "Stretch", "Rearrange",
    )
    return any(s.startswith(v + " ") or s == v for v in allowed)

def _reduce_to_single_action(step: str) -> str:
    """
    If model gives multi-step phrasing, keep only the first action clause.
    This preserves model variety while honoring 'one action only'.
    """
    s = (step or "").strip()
    if not s:
        return s

    # Split on common multi-step connectors
    lower = s.lower()
    cut_points = [" and ", " then ", ";", ","]
    for token in cut_points:
        idx = lower.find(token)
        if idx > 0:
            s = s[:idx].strip()
            break

    # Ensure it ends cleanly (optional)
    s = s.rstrip(".")  # don’t force punctuation; UI doesn’t need it
    return s


def _recent_microsteps(recent_followups: List[str], window: int = 3) -> List[str]:
    """
    Accepts either plain microsteps or blobs like 'MICROSTEP: ...'
    Returns the last N normalized microsteps (original casing not required here).
    """
    out: List[str] = []
    for item in (recent_followups or [])[-window:]:
        t = (item or "").strip()
        if not t:
            continue
        # If the stored text is a blob, try to extract after MICROSTEP:
        low = t.lower()
        if "microstep:" in low:
            # take everything after the last occurrence of 'microstep:'
            idx = low.rfind("microstep:")
            t = t[idx + len("microstep:"):].strip()
        out.append(t)
    return out


def _avoid_exact_repeat_microstep(
    candidate: str,
    recent_followups: Optional[List[str]],
    *,
    window: int = 3,
) -> bool:
    cand = _norm_microstep(candidate)
    if not cand:
        return False
    for prev in _recent_microsteps(recent_followups, window=window):
        if _norm_microstep(prev) == cand:
            return True
    return False

def _fallback_microstep_for_category(
    category: str,
    exclude: str = "",
    recent_followups: Optional[List[str]] = None,
    window: int = 3,
) -> str:
    """
    Deterministic: pick the first pool item that doesn't match `exclude`
    and doesn't repeat within the last `window` extracted microsteps.
    """
    pool = _CATEGORY_FALLBACK_POOL.get(category) or []
    if not pool:
        return "Place one hand on your chest."

    ex_norm = _normalize_step(exclude) if exclude else ""
    recent_steps = _recent_microsteps(recent_followups or [], window=window)
    recent_norm = {_normalize_step(s) for s in recent_steps if (s or "").strip()}

    for cand in pool:
        c = (cand or "").strip()
        if not c:
            continue
        c_norm = _normalize_step(c)
        if ex_norm and c_norm == ex_norm:
            continue
        if c_norm in recent_norm:
            continue
        return c

    return pool[0]  # deterministic safe fallback

def _rotate_category_fallback(*, category: str, current: str, recent_followups: list[str]) -> str:
    pool = _CATEGORY_FALLBACK_POOL.get(category) or []
    if not pool:
        return current

    recent = {(x or "").strip() for x in (recent_followups or [])}

    last = (_LAST_FALLBACK_BY_CATEGORY.get(category) or "").strip()
    start_idx = pool.index(last) + 1 if last in pool else 0

    for k in range(len(pool)):
        opt = pool[(start_idx + k) % len(pool)]
        if opt != current and opt not in recent:
            _LAST_FALLBACK_BY_CATEGORY[category] = opt
            return opt

    opt = pool[start_idx % len(pool)]
    _LAST_FALLBACK_BY_CATEGORY[category] = opt
    return opt
# -------------------------------------------------------------------
# Theme shaping (A.3) — now single-action safe
# -------------------------------------------------------------------

def _shape_microstep_for_theme(theme_label: str, microstep: str) -> str:
    """
    If model output is off-theme, replace with a theme-safe single action.
    (No 'and', no comma sequences.)
    """
    t = (theme_label or "Reflection").strip() or "Reflection"
    text = (microstep or "").strip()
    lower = text.lower()

    def has_any(words: tuple[str, ...]) -> bool:
        return any(w in lower for w in words)

    if t == "Presence":
        if not has_any(("breath", "abdomen", "body", "sensation", "exhale")):
            return THEME_FALLBACK_MICROSTEP["Presence"]

    elif t == "Clarity":
        if not has_any(("write", "sentence", "note", "name", "truth")):
            return THEME_FALLBACK_MICROSTEP["Clarity"]

    elif t == "Courage":
        if not has_any(("message", "send", "brave", "hard", "fear", "avoid")):
            return THEME_FALLBACK_MICROSTEP["Courage"]

    elif t == "Compassion":
        if not has_any(("heart", "kind", "soft", "gentle", "care")):
            return THEME_FALLBACK_MICROSTEP["Compassion"]

    elif t == "Purpose":
        if not has_any(("matters", "purpose", "meaning", "why", "serve")):
            return THEME_FALLBACK_MICROSTEP["Purpose"]

    elif t == "Balance":
        if not has_any(("pause", "rest", "limit", "pace", "slow")):
            return THEME_FALLBACK_MICROSTEP["Balance"]

    elif t == "Discipline":
        if not has_any(("timer", "begin", "start", "repeat", "routine", "space", "desk", "clear", "room")):
            return THEME_FALLBACK_MICROSTEP["Discipline"]

    elif t == "Devotion":
        if not has_any(("offer", "offering", "devotion", "gratitude", "palms")):
            return THEME_FALLBACK_MICROSTEP["Devotion"]

    elif t == "Surrender":
        if not has_any(("cannot control", "release", "let go", "surrender", "write")):
            return THEME_FALLBACK_MICROSTEP["Surrender"]

    elif t == "Calm-Sage":
        if not has_any(("sit", "quiet", "still", "slow", "upright")):
            return THEME_FALLBACK_MICROSTEP["Calm-Sage"]

    return text

# -------------------------------------------------------------------
# Category enforcement (A.8.1) — deterministic (POOL)
# -------------------------------------------------------------------

_CATEGORY_FALLBACK_POOL: Dict[str, list[str]] = {
    "posture": [
        "Sit upright for ten seconds.",
        "Set both feet flat on the floor.",
        "Relax your shoulders once.",
        "Place both hands on your thighs.",
    ],
    "touch": [
        "Place one hand on your chest.",
        "Rest one hand gently on your forearm.",
        "Press your palms together once.",
        "Place one hand on your abdomen.",
    ],
    "pacing": [
        "Pause for ten seconds before your next task.",
        "Pause without moving for ten seconds.",
        "Stop your hands for ten seconds.",
        "Look at one point for ten seconds.",
    ],
    "environment": [
        "Clear one small space in front of you.",
        "Slide one object slightly out of your way.",
        "Straighten one item near you.",
        "Close one open tab.",
    ],
    "breath": [
        "Notice the breath entering the nose.",
        "Count one slow breath silently.",
        "Exhale once through your nose.",
        "Feel one breath in your belly.",
    ],
}

# Keep a single “default” per category for hard-safe snaps
_CATEGORY_FALLBACK: Dict[str, str] = {
    k: v[0] for k, v in _CATEGORY_FALLBACK_POOL.items()
}

# ✅ add here (module-level “sticky memory” for cycling)
_LAST_FALLBACK_BY_CATEGORY: dict[str, str] = {}

def _cycle_fallback_for_category(
    category: str,
    exclude: str = "",
    recent_followups: Optional[List[str]] = None,
    window: int = 3,
) -> Tuple[str, Dict[str, object]]:
    """
    Deterministic cycling:
    - Start from last used fallback for this category (sticky memory)
    - Pick the next pool item that isn't `exclude` and doesn't repeat within last `window`
    - If everything collides, snap to primary fallback (pool[0])

    Returns: (chosen_step, meta)
    """
    meta: Dict[str, object] = {
        "category": category,
        "window": window,
        "exclude_norm": _normalize_step(exclude),
        "recent_norm": [],
        "last_norm": _normalize_step(_LAST_FALLBACK_BY_CATEGORY.get(category, "")),
        "picked_reason": "",
        "picked_index": None,
    }

    pool = _CATEGORY_FALLBACK_POOL.get(category) or []
    if not pool:
        meta["picked_reason"] = "empty_pool_default"
        return "Place one hand on your chest.", meta

    recent = _recent_microsteps(recent_followups or [], window=window)
    recent_norm = {_normalize_step(x) for x in recent if (x or "").strip()}
    meta["recent_norm"] = sorted(recent_norm)

    ex_norm = meta["exclude_norm"]
    last_norm = meta["last_norm"]

    # compute start index (one past last used)
    start_idx = 0
    if last_norm:
        for i, cand in enumerate(pool):
            if _normalize_step(cand) == last_norm:
                start_idx = (i + 1) % len(pool)
                break

    # iterate pool deterministically
    for k in range(len(pool)):
        idx = (start_idx + k) % len(pool)
        cand = pool[idx]
        cand_norm = _normalize_step(cand)

        if ex_norm and cand_norm == ex_norm:
            continue
        if cand_norm in recent_norm:
            continue

        _LAST_FALLBACK_BY_CATEGORY[category] = cand
        meta["picked_reason"] = "cycled"
        meta["picked_index"] = idx
        return cand, meta

    # everything collided: snap hard-safe
    primary = pool[0]
    _LAST_FALLBACK_BY_CATEGORY[category] = primary
    meta["picked_reason"] = "snap_primary_all_collided"
    meta["picked_index"] = 0
    return primary, meta


_CATEGORY_PATTERNS = {
    "breath": re.compile(r"\b(breath|breathe|exhale|inhale|belly|abdomen)\b", re.IGNORECASE),
    "touch": re.compile(r"\b(hand|hands|chest|heart|touch|palm|palms|abdomen|forearm)\b", re.IGNORECASE),
    "pacing": re.compile(r"\b(pause|slow|wait|timer|seconds?)\b|\b(\d+\s*seconds)\b|\b(ten\s+seconds)\b", re.IGNORECASE),
    "environment": re.compile(r"\b(desk|room|space|light|window|water|tabs?|close|object|items?|clear|straighten|slide)\b", re.IGNORECASE),
    "posture": re.compile(r"\b(sit|stand|upright|posture|spine|shoulders?|jaw|feet|foot|floor|thighs?)\b", re.IGNORECASE),
}

def _matches_category(step: str, category: str) -> bool:
    s = (step or "").strip()
    if not s:
        return False
    pat = _CATEGORY_PATTERNS.get((category or "").strip().lower())
    if not pat:
        return True
    return bool(pat.search(s))


def _pick_category_for_step(step: str, preferred: Optional[str] = None) -> str:
    """
    Deterministic category selection that reduces 'posture dominance'.
    - Honors preferred if it matches.
    - Otherwise: touch > breath > pacing > environment > posture (default).
    """
    s = (step or "").strip()
    pref = (preferred or "").strip().lower()

    # 1) If preferred matches, keep it.
    if pref in _CATEGORY_PATTERNS and _matches_category(s, pref):
        return pref

    # 2) Priority order (posture last to avoid stealing).
    priority = ("touch", "breath", "pacing", "environment", "posture")
    for cat in priority:
        if _matches_category(s, cat):
            return cat

    # 3) Safe default pool
    return (pref if pref in _CATEGORY_PATTERNS else "posture")

# -------------------------------------------------------------------
# Prompt composer
# -------------------------------------------------------------------

def _compose_prompt(
    theme: str,
    reflection_text: str,
    followup_note: str,
    practice_phase: Optional[str],
    recent_followups: Optional[List[str]] = None,
) -> str:
    """
    Build a structured, safe prompt for the Deepen Mentor.
    Must return EXACTLY two lines: INSIGHT + MICROSTEP.
    """

    theme_label = (theme or "Reflection").strip() or "Reflection"
    reflection_body = (reflection_text or "").strip() or "—"
    note_body = (followup_note or "").strip() or "—"

    tail_line = _extract_tail_line((reflection_text or "").strip() or "—")

    # Semantic category inference (debug + priority override)
    semantic_category = ""
    tail_lower = tail_line.lower()

    for cat in MICROSTEP_CATEGORIES:
        if _matches_category(tail_lower, cat):
            semantic_category = cat
            break

    history_items = (recent_followups or [])[-5:]
    history = " • ".join(h.strip() for h in reversed(history_items) if h and h.strip()) or "—"

    tone_block = (THEME_TONES.get(theme_label, "") or "").strip()

    # Safety flag (A.7) — keep, but don’t over-trigger
    unsafe = False
    lower_note = note_body.lower()
    if len(note_body) > 260:
        unsafe = True
    danger_terms = ("hurt", "harm", "worthless", "give up", "can't go on", "panic", "ashamed", "numb", "broken")
    if any(t in lower_note for t in danger_terms):
        unsafe = True

    if unsafe:
        safety_instruction = (
            "The note may be emotionally heavy. Be extra gentle. "
            "No therapy, no diagnosis, no solutions."
        )
    else:
        safety_instruction = "No therapy, no diagnosis, no complex advice."

    # Category selection (A.8)
    category = _select_microstep_category(theme_label, tail_line)
    category_hint = (MICROSTEP_HINTS.get(category, "") or "").strip()

    # Hard format + microstep contract (keep short and unambiguous)
    microstep_rules = (
        "MICROSTEP rules:\n"
        "- One single action under 2 minutes.\n"
        "- Use ONLY the chosen category.\n"
        "- No 'and'. No commas/semicolons. No sequences.\n"
        "- Not a mantra/affirmation.\n"
        "- Do NOT start with 'Breathe' and do NOT write inhale/exhale instructions.\n"
        "- Start with a verb: Take, Place, Sit, Stand, Look, Name, Write, Set, Pause.\n"
    )

    insight_rules = (
        "INSIGHT rules:\n"
        "- Exactly ONE sentence.\n"
        "- 8–22 words.\n"
        "- No directives ('you should/must/need to').\n"
        "- No cosmic certainty or bypassing.\n"
    )

    # Put the output contract LAST for maximum compliance
    return (
        f"{SYSTEM_PRIMER}\n"
        f"{tone_block}\n"
        f"{safety_instruction}\n\n"
        "Context:\n"
        f"- Theme: {theme_label}\n"
        f"- Practice phase: {practice_phase}\n"
        f"- Reflection tail: {tail_line or '—'}\n"
        f"- Recent follow-ups: {history}\n\n"
        "User reflection:\n"
        f"\"\"\"{reflection_body}\"\"\"\n\n"
        "User follow-up note:\n"
        f"\"\"\"{note_body}\"\"\"\n\n"
        f"Chosen microstep category (use ONLY this): {category}\n"
        f"{category_hint}\n\n"
        f"{insight_rules}\n"
        f"{microstep_rules}\n"
        "Return EXACTLY two lines and nothing else:\n"
        "INSIGHT: <...>\n"
        "MICROSTEP: <...>\n"
    )

def _is_near_empty(text: str, *, min_alpha: int = 3) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return True

    # Normalize common wrappers like "tail: ok."
    if t.startswith("tail:"):
        t = t.replace("tail:", "", 1).strip()

    if t in {"ok", "ok.", "k", "fine", "n/a", "na", "none", "-", "—", "...", "…"}:
        return True

    alpha = re.sub(r"[^a-z]+", "", t)
    return len(alpha) < min_alpha


def _normalize_mood_for_no_signal(reflection_text: str, followup_note: str, mood: str) -> str:
    if _is_near_empty(reflection_text) and _is_near_empty(followup_note):
        return "soft"  # or "clear" if you prefer
    return mood

def _silence_stillness_for(mood: str) -> str:
    """
    Stillness line used when silence contract is active.
    Keep it short, neutral, and safe for all moods.
    """
    m = (mood or "").strip().lower()

    if m in {"storm", "anger", "intense"}:
        return "Stillness: unclench your jaw and exhale slowly."
    if m in {"sad", "heavy", "low"}:
        return "Stillness: place a hand on your chest and soften your breath."
    if m in {"anxious", "restless", "wired"}:
        return "Stillness: feel your feet and take one slow breath."
    if m in {"soft", "calm", "neutral"}:
        return "Stillness: return to one easy breath."

    return "Stillness: return to one calm breath."

def _silence_output(*, mood: str) -> tuple[str, None, str]:
    """
    IMPORTANT: Always return (stillness, insight, microstep).
    For silence contract: insight must be None (by contract),
    microstep should be a gentle default microstep string.
    """
    stillness = _silence_stillness_for(mood)
    insight = None
    microstep = "Return to one calm breath."
    return stillness, insight, microstep

def _return_silence_contract(
    *,
    theme_label: str,
    mood: str,
    silenced: bool,
    silence_reason: Optional[str],
    stillness: str,
    decision_path: List[str],
    dbg: dict,
    # optional presence debug bundle (pass if you have it at that point)
    presence_payload: Optional[dict] = None,
) -> Tuple[str, Optional[str], str]:
    """
    Single silence return contract for ALL silence exits.
    Always returns (stillness, insight=None, microstep="").
    Also snapshots _last_debug consistently.
    """
    insight = None
    microstep = ""

    _last_debug.clear()
    payload = {
        "theme": theme_label,
        "mood": mood,
        "silenced": bool(silenced),
        "silence_reason": silence_reason,
        "silence_rule": dbg.get("silence_rule") or dbg.get("rule"),
        "stillness": stillness,
        "final_insight": insight,
        "final_microstep": microstep,
        "insight_source": "silence_contract",
        "microstep_source": "silence_contract",
        "decision_path": " > ".join(decision_path),
    }
    if isinstance(presence_payload, dict):
        payload.update(presence_payload)

    _last_debug.update(payload)
    return stillness, insight, microstep

# -------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------

def generate_deepen_insight(
    theme: str,
    reflection_text: str,
    followup_note: str,
    recent_followups: Optional[List[str]] = None,
) -> Tuple[str, Optional[str], str]:
    """
    Final pipeline (SEALED):
        0) Mood detect (single path)
        1) C5 Silence gate (MUST be before any AI/model work) + early return on silence
        1b) Presence inference snapshot (runs even on silence; debug + memory)
        2) Safe model call (lazy import, circular-safe)
        2b) AI unavailable → force silence contract + return
        3) Prefix strip + microstep reduction
        4) Theme fallback if empty
        5) Tone align (non-blanking)
        6) Theme shaping
        7) Category selection + mood bias
        8) Category enforcement (deterministic fallback + rotation)
        9) Guardrails (verb-first, no mantra, no multi-step)
       10) Hard-safe fallback
       11) Anti-repeat (FINAL pass, deterministic)
       12) Final polish
       13) Debug capture (pure snapshot) + memory write
    """
    silenced = False
    silence_reason = None
    dbg = {}

    theme_label = (theme or "Reflection").strip() or "Reflection"
    recent_followups = list(recent_followups or [])

    # Normalize inputs (single source of truth)
    reflection_text = (reflection_text or "").strip()
    followup_note = (followup_note or "").strip()

    # One norm_text used everywhere (mood, bias, debug)
    norm_text = (reflection_text + "\n" + followup_note).strip()

    # --- Debug hygiene (A) ---
    decision_path: List[str] = []

    def _dp(step: str) -> None:
        decision_path.append(step)

    def _norm_s(x) -> str:
        return (x or "").strip()

    def _short_err(e: str, limit: int = 180) -> str:
        s = _norm_s(e)
        return s if len(s) <= limit else (s[:limit] + "…")

    def _is_rate_limited(msg: str) -> bool:
        m = (msg or "").lower()
        return ("rate limit" in m) or ("429" in m) or ("too many requests" in m) or ("cooldown" in m)

    # -------------------------
    # 0) Mood detect (single path)
    # -------------------------
    no_signal = _is_near_empty(reflection_text, min_alpha=4) and _is_near_empty(followup_note, min_alpha=4)
    if no_signal:
        mood = "soft"
        mood_source = "forced_no_signal"
    else:
        mood = detect_mood(norm_text)
        mood_source = "detect_mood"

    # Apply your downstream “no signal” normalization rule (kept)
    mood = _normalize_mood_for_no_signal(reflection_text, followup_note, mood)

    dbg["mood_source"] = mood_source
    dbg["norm_text_preview"] = norm_text[:80]
    _dp(f"mood={mood}")

    grounded = mood in ("drained", "soft") and not silenced

    # -------------------------
    # 1) C5 — Silence gate (BEFORE any AI/model work)
    # -------------------------
    subdued_mode = bool(os.getenv("AGI_SUBDUED_MODE_DEFAULT", "0") == "1")
    # OR if you pass from UI, use that value instead
    silenced, silence_reason = should_silence(
        reflection_text=reflection_text,
        followup_note=followup_note,
        recent_followups=recent_followups,
        mood=mood,
        dbg=dbg,
        subdued_mode=subdued_mode,
    )
    
    # --- defaults so we never hit UnboundLocalError ---
    raw_insight = ""
    raw_second = ""
    model_error = ""
    model_rate_limited = False

    _last_debug["silenced"] = bool(silenced)
    _last_debug["silence_reason"] = silence_reason
    _last_debug["silence_rule"] = dbg.get("silence_rule") or dbg.get("rule")

    _dp("silence_gate=hit" if silenced else "silence_gate=pass")

    print("SILENCE DBG:", {
    "mood": mood,
    "rule": dbg.get("silence_rule"),
    "len": dbg.get("silence_text_len"),
    "recent_n": dbg.get("silence_recent_n"),
    })

    dbg["subdued"] = mood in ("drained", "soft")

    # --- Load presence continuity from reflection_state (D2) ---
    presence_stage_prev = 0
    presence_drift_prev = 0
    state_row = None

    try:
        import streamlit as st
        from agi.db import get_client as get_supabase
        from agi.auth import S_USER_ID

        sb = get_supabase()
        user_id = st.session_state.get(S_USER_ID)
    except Exception as e:
        sb = None
        user_id = None
        if os.getenv("AGI_DEBUG") == "1":
            print("presence: sb/user load failed:", str(e)[:160])

    try:
        from agi.persistence.state import fetch_reflection_state
        if sb and user_id:
            state_row = fetch_reflection_state(sb, user_id=str(user_id))
            if state_row:
                presence_stage_prev = int(state_row.get("last_presence_stage") or 0)
                presence_drift_prev = int(state_row.get("presence_drift_hits") or 0)
    except Exception as e:
        if os.getenv("AGI_DEBUG") == "1":
            print("presence: fetch_reflection_state failed:", str(e)[:160])

    presence_text = (reflection_text + "\n" + followup_note).strip()

    presence_stage_today, presence_reason = infer_presence_stage(
        reflection_text=presence_text,
        mood=mood,
        silenced=silenced,
        )

    presence_update = presence_update_stage(
    stage_prev=presence_stage_prev,
    stage_today=presence_stage_today,
    silenced=silenced,
    mood=mood,
    drift_hits_prev=presence_drift_prev,
    silence_reason=silence_reason,
)

    presence_stage_final = presence_update.stage_final
    presence_drift_new = presence_update.drift_hits_new
    presence_dbg = presence_update.dbg

    if os.getenv("AGI_DEBUG") == "1":
        print("PRESENCE DBG:", {
            "prev": presence_stage_prev,
            "today": presence_stage_today,
            "final": presence_stage_final,
            "drift_prev": presence_drift_prev,
            "drift_new": presence_drift_new,
            "reason": presence_reason,
        })

    # --- Rhythm intelligence (tiny seed) ---
    response_mode = infer_response_mode(
        presence_stage=presence_stage_final,
        drift_hits=(presence_drift_prev or 0) + (presence_drift_new or 0),
        silenced=bool(silenced),
        mood=mood,
    )

    if os.getenv("AGI_DEBUG") == "1":
        print("RHYTHM DBG:", {
            "mode": response_mode
        })

    # --- Dharma phase inference (practice readiness) ---
    practice_phase = infer_practice_phase(
        presence_stage=presence_stage_final,
        drift_hits=(presence_drift_prev or 0) + (presence_drift_new or 0),
        silenced=bool(silenced),
        response_mode=response_mode,
    )

    if os.getenv("AGI_DEBUG") == "1":
        print("DHARMA DBG:", {
            "practice_phase": practice_phase
        })
    # --- Persist presence (D2) ---
    # Option C "single writer":

    if silenced:
        stillness = _silence_stillness_for(mood)
        presence_payload = {
            "presence_stage_prev": presence_stage_prev,
            "presence_stage_today": presence_stage_today,
            "presence_stage_final": presence_stage_final,
            "presence_stage_label": presence_stage_label(presence_stage_final),
            "presence_reason": presence_reason,
            "presence_drift_hits_prev": presence_drift_prev,
            "presence_drift_hits_new": presence_drift_new,
            "presence_dbg": presence_dbg,
        }
        return _return_silence_contract(
            theme_label=theme_label,
            mood=mood,
            silenced=True,
            silence_reason=silence_reason,
            stillness=stillness,
            decision_path=decision_path,
            dbg=dbg,
            presence_payload=presence_payload,
        )

    # -------------------------
    # Normal path continues
    # -------------------------
    tail_line = _extract_tail_line(reflection_text or "—")
    stillness = _select_stillness_note(theme_label, tail_line)
    prompt = _compose_prompt(
        theme_label,
        reflection_text,
        followup_note,
        practice_phase,
        recent_followups
    )

    # -------------------------
    # 2) Safe model call (lazy import, circular-safe)
    # -------------------------

    raw_insight = ""
    raw_second = ""
    model_error = ""
    model_rate_limited = False

    def _is_deepen_test_mode() -> bool:
        import os
        return os.getenv("DEEPEN_TEST_MODE") == "1" or os.getenv("DEEPEN_NO_AI") == "1"

    test_mode = _is_deepen_test_mode()

    if test_mode:
        _dp("model=skipped:test_mode")
    else:
        try:
            # Lazy import prevents circular import at module load
            from agi.ai import ai_generate_deepen

            raw_insight, raw_second = ai_generate_deepen(theme_label, prompt)
            _dp("model=ok")

        except Exception as e:
            model_error = str(e)
            model_rate_limited = _is_rate_limited(model_error)

            dbg["model_fallback_reason"] = (
                "rate_limited" if model_rate_limited else "model_error"
            )
            dbg["ai_error"] = model_error[:160]

            # Do NOT re-raise — silence logic handles downstream behavior
            raw_insight = ""
            raw_second = ""

            _dp("model=error_handled")

    # 2b) AI unavailable -> force silence contract + return
    if dbg.get("model_fallback_reason") in ("rate_limited", "model_error"):
        silenced = True
        silence_reason = "ai_unavailable"

        dbg["silenced"] = True
        dbg["silence_reason"] = silence_reason
        dbg["silence_rule"] = "ai_unavailable"
        _dp("model=ai_unavailable_to_silence")

        stillness = _silence_stillness_for(mood)

        # --- Presence payload (freeze on silence) ---
        # Make sure these vars exist earlier in the function:
        # presence_stage_prev, presence_drift_prev, presence_stage_today, presence_reason
        presence_payload = {
            "presence_stage_prev": presence_stage_prev,
            "presence_stage_today": presence_stage_today,
            "presence_stage_final": presence_stage_prev,      # freeze
            "presence_stage_label": presence_stage_label(presence_stage_prev),
            "presence_reason": "ai_unavailable_freeze",
            "presence_drift_hits_prev": presence_drift_prev,
            "presence_drift_hits_new": presence_drift_prev,   # freeze
            "presence_dbg": {"note": "forced_silence_on_ai_unavailable"},
        }

        return _return_silence_contract(
            theme_label=theme_label,
            mood=mood,
            silenced=True,
            silence_reason=silence_reason,
            stillness=stillness,
            decision_path=decision_path,
            dbg=dbg,
            presence_payload=presence_payload,
        )

    # -------------------------
    # 3) Prefix strip + microstep reduction
    # -------------------------
    def strip_prefix(s: str) -> str:
        s = (s or "").strip()
        bad_prefixes = (
            "INSIGHT:", "Insight:", "INSIGHT -", "Insight -", "**INSIGHT:**",
            "MICROSTEP:", "Microstep:", "Micro-step:", "Micro-step -", "**MICROSTEP:**",
        )
        for p in bad_prefixes:
            if s.startswith(p):
                return s[len(p):].strip()
        return s

    insight = strip_prefix(raw_insight)
    microstep = strip_prefix(raw_second)
    microstep = _reduce_to_single_action(microstep)

    # Track sources (A)
    insight_source = "model" if (insight or "").strip() else "fallback"
    

    used_fallback = False
    shaped = False
    guardrail_adjusted = False
    category_adjusted = False
    microstep_reused = False
    repeat_avoided = False

    # -------------------------
    # 4) Theme fallback if empty
    # -------------------------
    if not (insight or "").strip():
        insight = THEME_FALLBACK_INSIGHT.get(theme_label, THEME_FALLBACK_INSIGHT["Clarity"])
        used_fallback = True
        insight_source = "fallback"
        _dp("insight=fallback")

    # -------------------------
    # 5) Tone align (non-blanking)
    # -------------------------
    before_insight = insight
    insight = _align_insight_tone(theme_label, mood, insight)
    insight_tone_adjusted = (insight != before_insight)

    if not (insight or "").strip():
        insight = before_insight
        insight_tone_adjusted = False

    # -------------------------
    # 6) Theme shaping
    # -------------------------
    theme_sig_strength, theme_sig_hits = _theme_signature_strength(theme_label, insight)
    theme_signature_decay = (
        theme_label in THEME_SIGNATURES
        and len((insight or "").strip()) > 40
        and theme_sig_hits == 0
    )

    # -------------------------
    # Fallback microstep (Dharma-aware, category-safe)
    # -------------------------
    if not (microstep or "").strip():
        used_fallback = True
        _dp("microstep=fallback_dharma")
    

    # -------------------------
    # 6) Theme shaping (A.3)
    # -------------------------
    before_shape = microstep
    microstep = _shape_microstep_for_theme(theme_label, microstep)
    if microstep != before_shape:
        shaped = True

    pre_category_microstep = microstep

    # -------------------------
    # 7) Category selection + mood bias
    # -------------------------
    # --- semantic category (optional) ---
    semantic_category = ""
    tl = (tail_line or "").lower()

    for cat in MICROSTEP_CATEGORIES:
        if _matches_category(tl, cat):
            semantic_category = cat
            break

    # --- Dharma bias for microstep category ---
    preferred_cat = preferred_microstep_category(practice_phase)

    base_category = semantic_category or preferred_cat or _select_microstep_category(
        theme_label, tail_line
    )

    chosen_category = base_category

    dbg["category_selected_by"] = "semantic" if semantic_category else "hash"
    dbg["semantic_category"] = semantic_category

    biased_category = ""
    category_bias_reason = "already_matches"

    # Rotation debug defaults
    dbg["fallback_rotated"] = False
    dbg["fallback_rotated_from"] = ""
    dbg["fallback_rotated_to"] = ""

    # Repeat debug defaults
    dbg["repeat_hit"] = False
    dbg["repeat_action"] = ""
    dbg["repeat_match"] = ""

    # -------------------------
    # 8) Category enforcement (deterministic fallback + rotation)
    # -------------------------
    if chosen_category and (not _matches_category(microstep, chosen_category)):

        biased = _apply_mood_category_bias(chosen_category, mood, norm_text=norm_text)

        if biased != chosen_category:
            chosen_category = biased
            biased_category = biased
            category_bias_reason = "bias_applied"
        else:
            category_bias_reason = "no_bias"

        base_fallback, cycle_meta = _cycle_fallback_for_category(
            category=chosen_category,
            exclude=microstep,
            recent_followups=recent_followups,
        )
        dbg["fallback_cycle_reason"] = cycle_meta["picked_reason"]
        dbg["fallback_cycle_index"] = cycle_meta["picked_index"]
        dbg["fallback_cycle_last"] = cycle_meta["last_norm"]

        rotated_step, reused, repeat_meta = _avoid_repeat_microstep(
            microstep=base_fallback,
            chosen_category=chosen_category,
            recent_followups=recent_followups,
        )

        microstep = rotated_step
        microstep_reused = bool(reused)
        repeat_avoided = bool(reused)

        category_adjusted = True
        used_fallback = True

        dbg["fallback_rotated"] = ((microstep or "").strip() != (base_fallback or "").strip())
        dbg["fallback_rotated_from"] = base_fallback
        dbg["fallback_rotated_to"] = microstep

        if isinstance(repeat_meta, dict):
            dbg["repeat_hit"] = bool(repeat_meta.get("repeat_hit", False))
            dbg["repeat_action"] = (repeat_meta.get("repeat_action") or "")
            dbg["repeat_match"] = (repeat_meta.get("repeat_match") or "")

        _dp("category_applied")

    # -------------------------
    # 9) Guardrails (verb-first, no mantra, no multi-step)
    # -------------------------
    microstep = (microstep or "").strip()
    invalid = (not _is_valid_microstep(microstep))

    if (
        invalid
        or _is_mantra_like(microstep)
        or (not _starts_with_allowed_verb_titlecase(microstep))
        or _looks_multi_step(microstep)
    ):
        guardrail_adjusted = True
        used_fallback = True
        _dp("guardrails=replaced")

        guard_cat = (chosen_category or base_category or "posture")

        base_fallback, cycle_meta = _cycle_fallback_for_category(
            category=guard_cat,
            exclude=microstep,
            recent_followups=recent_followups,
        )
        dbg["fallback_cycle_reason"] = cycle_meta["picked_reason"]
        dbg["fallback_cycle_index"] = cycle_meta["picked_index"]
        dbg["fallback_cycle_last"] = cycle_meta["last_norm"]

        microstep = _reduce_to_single_action(base_fallback)

        dbg["fallback_rotated"] = False
        dbg["fallback_rotated_from"] = base_fallback
        dbg["fallback_rotated_to"] = base_fallback

    # -------------------------
    # 10) Hard-safe fallback
    # -------------------------
    if (
        (not _is_valid_microstep(microstep))
        or _is_mantra_like(microstep)
        or (not _starts_with_allowed_verb_titlecase(microstep))
        or _looks_multi_step(microstep)
    ):
        microstep = "Place one hand on your chest."
        used_fallback = True
        guardrail_adjusted = True
        _dp("hard_safe=fired")

    # -------------------------
    # 11) Anti-repeat (FINAL pass, deterministic)
    # -------------------------
    final_cat = _pick_category_for_step(microstep, preferred=(chosen_category or base_category))

    rotated, reused, repeat_meta = _avoid_repeat_microstep(
        microstep=microstep,
        chosen_category=final_cat,
        recent_followups=recent_followups,
    )
    if reused:
        microstep = rotated
        microstep_reused = True
        repeat_avoided = True
        _dp("repeat_rotated")

        if isinstance(repeat_meta, dict):
            dbg["repeat_hit"] = bool(repeat_meta.get("repeat_hit", True))
            dbg["repeat_action"] = (repeat_meta.get("repeat_action") or "rotated")
            dbg["repeat_match"] = (repeat_meta.get("repeat_match") or "")

    # -------------------------
    # 12) Final polish
    # -------------------------
    insight = (insight or "").strip()
    microstep = (microstep or "").strip()

    if insight and insight[-1] not in ".!?":
        insight += "."

    if microstep and microstep[-1] not in ".!?":
        microstep += "."

    if not insight:
        insight = (
            THEME_FALLBACK_INSIGHT.get(theme_label)
            or THEME_FALLBACK_INSIGHT.get("Clarity")
            or "You are already here."
        )
        used_fallback = True
        insight_source = "fallback"

    # Rate-limit override (B)
    if model_rate_limited and insight_source == "fallback":
        insight_source = "fallback_due_to_rate_limit"

    # -------------------------
    # 12.5) Resolve attribution (FINAL, ONCE)
    # -------------------------
    microstep_source = resolve_microstep_source(
        silenced=silenced,
        model_rate_limited=model_rate_limited,
        used_fallback=used_fallback,
        category_adjusted=category_adjusted,
        guardrail_adjusted=guardrail_adjusted,
        raw_model_microstep=raw_second,
        pre_category_microstep=pre_category_microstep,
        final_microstep=microstep,
    )

    microstep_dominance = resolve_microstep_dominance(
        silenced=False,
        model_rate_limited=model_rate_limited,
        used_fallback=used_fallback,
        guardrail_adjusted=guardrail_adjusted,
        pre_category_microstep=(pre_category_microstep or "").strip(),
        raw_model_microstep=(raw_second or "").strip(),
        final_microstep=microstep,
    )

    # -------------------------
    # 13) Debug capture (pure snapshot) + memory write
    # -------------------------
    _last_debug.clear()
    _last_debug.update({
        "theme": theme_label,
        "mood": mood,

        "base_category": base_category,
        "biased_category": biased_category,
        "category_bias_reason": category_bias_reason,
        "chosen_category": chosen_category,

        "used_fallback": bool(used_fallback),
        "shaped": bool(shaped),
        "category_adjusted": bool(category_adjusted),
        "guardrail_adjusted": bool(guardrail_adjusted),

        "model_rate_limited": bool(model_rate_limited),
        "model_error": _short_err(model_error),
        "raw_model_insight": (raw_insight or "").strip(),
        "raw_model_microstep": (raw_second or "").strip(),

        "stillness": stillness,
        "final_insight": insight,
        "final_microstep": microstep,
        "pre_category_microstep": pre_category_microstep,

        "insight_source": insight_source,
        "microstep_source": microstep_source,
        "microstep_dominance": microstep_dominance,
        "decision_path": " > ".join(decision_path),

        "insight_tone_adjusted": bool(insight_tone_adjusted),
        "pre_tone_insight": (before_insight or "").strip(),

        "theme_signature_strength": theme_sig_strength,
        "theme_signature_hits": theme_sig_hits,
        "theme_signature_decay": theme_signature_decay,

        "silenced": bool(silenced),
        "silence_reason": silence_reason,
        "silence_rule": dbg.get("silence_rule"),

        # Presence debug (D-2b)
        "presence_stage_prev": presence_stage_prev,
        "presence_stage_today": presence_stage_today,
        "presence_stage_final": presence_stage_final,
        "presence_stage_label": presence_stage_label(presence_stage_final),
        "presence_reason": presence_reason,
        "presence_drift_hits_prev": presence_drift_prev,
        "presence_drift_hits_new": presence_drift_new,
        "presence_dbg": presence_dbg,

        "model_success": (not model_error) and (
            bool((raw_insight or "").strip()) or bool((raw_second or "").strip())
        ),

        "repeat_avoided": bool(repeat_avoided),
        "microstep_reused": bool(microstep_reused),
        "last_microstep": (recent_followups[-1] if recent_followups else ""),

        "fallback_rotated": bool(dbg.get("fallback_rotated", False)),
        "fallback_rotated_from": (dbg.get("fallback_rotated_from") or ""),
        "fallback_rotated_to": (dbg.get("fallback_rotated_to") or ""),

        "repeat_hit": bool(dbg.get("repeat_hit", False)),
        "repeat_action": (dbg.get("repeat_action") or ""),
        "repeat_match": (dbg.get("repeat_match") or ""),

        "practice_phase": practice_phase,
        "response_mode": response_mode,
    })

    _attach_presence_debug(
        dbg=_last_debug,
        reflection_text=presence_text,
        mood=mood,
        silenced=False,
        silence_reason=None,
        presence_stage_prev=presence_stage_prev,
        presence_drift_hits_prev=presence_drift_prev,
    )
    
    print("🧠 E1 memory write reached")

    drift_new = int(presence_drift_new or 0)
    print("DRIFT PIPELINE TEST:", drift_new)

    # -------------------------
    # E1) Memory write (record-only, non-intrusive)
    # -------------------------

    mem_enabled = os.getenv("AGI_MEMORY_ENABLED", "0") == "1"
    mem_rc = {"enabled": mem_enabled, "written": False, "error": None}

    if mem_enabled:
        try:
            # Import locally to avoid circular imports at module load time
            from agi.memory import record_reflection_memory

            mem_rc = record_reflection_memory(
                theme=theme_label,                     # use normalized label
                mood=mood,
                microstep=(microstep or ""),
                insight=(insight if insight is not None else None),
                silenced=bool(silenced),
                silence_reason=silence_reason,
                presence_stage=presence_stage_final,   # ✅ use the actual final var
                presence_drift_hits_new=drift_new,  # ✅ add this
            )
        except Exception as e:
            mem_rc = {"enabled": True, "written": False, "error": str(e)[:160]}

    # Attach to debug snapshot (safe)
    _last_debug["memdbg"] = mem_rc

    # -------------------------
    # D2.5) Weekly Presence Snapshot Refresh
    # -------------------------
    try:
        if sb and user_id:
            from agi.persistence.snapshots import refresh_weekly_presence_snapshot

            rc_snap = refresh_weekly_presence_snapshot(
                sb,
                user_id=str(user_id),
            )

            if os.getenv("AGI_DEBUG") == "1":
                print("SNAPSHOT DBG:", rc_snap)

    except Exception as e:
        if os.getenv("AGI_DEBUG") == "1":
            print("SNAPSHOT DBG: failed:", str(e)[:160])

    # Only print in debug mode
    if os.getenv("AGI_DEBUG") == "1":
        print("MEMDBG:", mem_rc)

    return stillness, insight, microstep