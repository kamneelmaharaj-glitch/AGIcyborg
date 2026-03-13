from __future__ import annotations

import re


FORBIDDEN_WORDS = {
    "breathe", "inhale", "exhale",
    "reflect on", "consider", "think about",
    "try to", "practice", "remember to",
}

START_VERBS = {
    "take", "place", "sit", "stand", "look",
    "name", "write", "set", "pause",
}


def is_valid_microstep(text: str) -> bool:
    """
    Enforces the AGIcyborg microstep contract.
    """

    if not text:
        return False

    step = text.strip()

    # Must be a single sentence
    if step.count(".") > 1:
        return False

    # No commas or sequences
    if "," in step or ";" in step:
        return False

    # Prevent instruction chains
    if " and " in step.lower():
        return False

    # Word limit (very short)
    if len(step.split()) > 12:
        return False

    lower = step.lower()

    # Forbidden words
    for w in FORBIDDEN_WORDS:
        if w in lower:
            return False

    # Must start with action verb
    first_word = lower.split()[0]

    if first_word not in START_VERBS:
        return False

    return True