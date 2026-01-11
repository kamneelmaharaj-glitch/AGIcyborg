# agi/silence_contract.py

from __future__ import annotations

from typing import Optional, Tuple
import re


_NO_SIGNAL_TOKENS = {
    "", "—", "-", "–", "…", "...", "… … …", "... ... ...",
    "n/a", "na", "none", "null",
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
    if text in _NO_SIGNAL_TOKENS:
        return True

    # Only punctuation / separators (e.g., "----", "....", "…", "— —")
    if re.fullmatch(r"[\-–—\.\,\;\:\!\?\s]+", text or ""):
        return True

    # Very short “filler” lines (after normalization)
    if len(text) <= 2 and text in {"ok", "k"}:
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

def should_silence(
    *,
    reflection_text: str,
    followup_note: str,
    recent_followups: Optional[list[str]] = None,
    mood: str,
    dbg: Optional[dict] = None,
) -> Tuple[bool, Optional[str]]:
    """
    C5 — Silence Decision Contract

    Returns:
        (silence: bool, reason: str | None)

    This function must be:
    - deterministic
    - non-creative
    - non-rewriting
    """

    text = _normalize_text(reflection_text, followup_note)
    recent_followups = recent_followups or []

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

    # 3) Followup saturation → silence
    # (C5 intent: if user keeps poking without new info, hold stillness)
    if len(recent_followups) >= 3:
        if dbg is not None:
            dbg["silence_rule"] = "followup_saturation"
        return True, "followup_saturation"

    # 4) Externalized authority demand → silence
    if _is_externalized_authority(text):
        if dbg is not None:
            dbg["silence_rule"] = "externalized_authority"
        return True, "externalized_authority"

    if dbg is not None:
        dbg["silence_rule"] = "none"
    return False, None