# agi/silence_contract.py

"""
Silence is NOT:
- low energy
- sadness
- tiredness
- uncertainty

Silence IS:
- no signal
- saturation
- emotional overload
- authority outsourcing
"""

from __future__ import annotations

from typing import Optional, Tuple
import re


_NO_SIGNAL_TOKENS = {
    "", "—", "-", "–", "…", "...", "… … …", "... ... ...",
    "n/a", "na", "none", "null",
}

_NO_SIGNAL_PHRASES = {
    "i dont know", "i don't know", "dont know", "don't know",
    "not sure", "no idea", "idk",
    "n/a", "na", "none", "nothing", "empty",
}

# Explicit “hand over authority” phrases
_EXTERNAL_AUTHORITY_PHRASES = (
    "fix me",
    "just tell me the answer",
    "give me the answer",
    "tell me the answer",
    "tell me what to do",
    "what should i do",
)

def _normalize_text(reflection_text: str, followup_note: str) -> str:
    t = ((reflection_text or "") + "\n" + (followup_note or "")).strip().lower()
    # collapse whitespace
    t = re.sub(r"\s+", " ", t)
    # normalize unicode ellipsis to "..."
    t = t.replace("…", "...")
    return t.strip()


def _is_no_signal(text: str) -> bool:
    t = (text or "").strip().lower()

    # 0) Empty or whitespace
    if not t:
        return True

    # 1) Explicit no-signal tokens
    if t in _NO_SIGNAL_TOKENS:
        return True

    # 2) Only punctuation / separators
    if re.fullmatch(r"[\-–—\.\,\;\:\!\?\s…]+", t):
        return True

    # 3) Very short filler responses
    if t in {"ok", "k"}:
        return True

    # 4) Phrase-level no-signal (exact or short “contains”)
    if t in _NO_SIGNAL_PHRASES:
        return True
    if any(p in t for p in _NO_SIGNAL_PHRASES) and len(t) <= 24:
        return True

    # 5) Low-information fragments
    alnum = re.sub(r"[^a-z0-9]+", "", t)
    if len(alnum) <= 2 and len(t) <= 6:
        return True

    return False

def _is_externalized_authority(text: str) -> bool:
    # If text is mostly a directive demand and not much else, silence.
    # But if user gives real context (longer text), we avoid silencing too aggressively.
    if any(p in text for p in _EXTERNAL_AUTHORITY_PHRASES):
        # Allow if they ALSO provided meaningful context
        # (keeps “tell me what to do” from silencing when they wrote a full reflection)
        if len(text) >= 140:
            return False
        return True
    return False

# SILENCE CONTRACT (v1)
# Silence is a valid completion state.
# It is not an error, fallback, or absence.
# No AI output is required when silence is active.

def should_silence(
    *,
    reflection_text: str,
    followup_note: str,
    recent_followups: Optional[list[str]] = None,
    mood: str,
    dbg: Optional[dict] = None,
    # NEW: optional manual override (UI can drive this)
    subdued_mode: bool = False,
) -> Tuple[bool, Optional[str]]:
    """
    C5 — Silence Decision Contract

    Returns:
        (silence: bool, reason: str | None)

    Deterministic, non-creative, non-rewriting.
    """

    text = _normalize_text(reflection_text, followup_note)
    recent_followups = recent_followups or []

    # Helpful debug signals (safe + deterministic)
    if dbg is not None:
        dbg["silence_text_len"] = len(text or "")
        dbg["silence_recent_n"] = len(recent_followups)
        dbg["silence_mood_in"] = mood
        dbg["silence_subdued_mode"] = bool(subdued_mode)

    # 0) Manual subdued → silence (recommended UX)
    if subdued_mode:
        if dbg is not None:
            dbg["silence_rule"] = "manual_subdued"
        return True, "manual_subdued"

    # 1) Emotional overload → silence
    if mood in ("overwhelmed", "heavy"):
        if dbg is not None:
            dbg["silence_rule"] = "emotional_overload"
        return True, "emotional_overload"

    # 2) No signal → silence
    if _is_no_signal(text):
        if dbg is not None:
            dbg["silence_rule"] = "no_signal"
        return True, "no_signal"

    # 3) Followup saturation → silence ONLY when current input is low-signal / repetitive
    # Intent: if user keeps poking without new substance, hold stillness.
    if len(recent_followups) >= 3:
        # If they wrote something meaningful now, do NOT silence.
        # We treat "meaningful" as not-no-signal.
        # (If you want stricter: add a second heuristic like "few alpha chars".)
        if _is_no_signal(_normalize_text("", followup_note)):
            if dbg is not None:
                dbg["silence_rule"] = "followup_saturation_no_new_signal"
            return True, "followup_saturation_no_new_signal"

    # 4) Externalized authority demand → silence
    if _is_externalized_authority(text):
        if dbg is not None:
            dbg["silence_rule"] = "externalized_authority"
        return True, "externalized_authority"

    if dbg is not None:
        dbg["silence_rule"] = "none"
    return False, None