from __future__ import annotations

import re

MAX_MIRROR_CHARS = 140

PREFIXES = (
    "You noticed",
    "It seems",
    "There was a sense",
    "You became aware",
)

def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())

def _extract_core(reflection: str) -> str:
    """
    Very light reduction of reflection text.
    We take the first sentence or first clause to mirror.
    """
    if not reflection:
        return ""

    # split by sentence
    parts = re.split(r"[.!?]", reflection)
    core = parts[0].strip()

    # remove leading filler
    core = re.sub(r"^(today|i|i felt|i noticed|i think)\s+", "", core, flags=re.I)

    return core

def generate_mirror(reflection_text: str, mood: str, presence_stage: int) -> str:
    """
    Generate a short awareness mirror from the reflection.
    Deterministic and intentionally simple.
    """

    reflection = _normalize(reflection_text)
    if not reflection:
        return "You noticed something worth pausing with."

    core = _extract_core(reflection)

    low = (reflection_text or "").lower()

    if "steady" in low:
        return "There was a sense of steadiness."
    if "balanced" in low:
        return "You noticed a feeling of balance."
    if "calm" in low:
        return "There was a sense of calm present."

    prefix = PREFIXES[presence_stage % len(PREFIXES)]

    mirror = f"{prefix} {core.lower()} in you."

    mirror = _normalize(mirror)

    # enforce length
    if len(mirror) > MAX_MIRROR_CHARS:
        mirror = mirror[:MAX_MIRROR_CHARS].rstrip(" ,;:-")
        if mirror[-1] not in ".!?":
            mirror += "."

    return mirror