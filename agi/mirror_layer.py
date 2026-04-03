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
    if not reflection:
        return ""

    parts = re.split(r"[.!?]", reflection)
    core = parts[0].strip()

    core = re.sub(r"^(i feel|i felt|i noticed|i think|today|i)\s+", "", core, flags=re.I)

    return core


def generate_mirror(reflection_text: str, mood: str, presence_stage: int) -> str:
    reflection = _normalize(reflection_text)
    if not reflection:
        return "Something here feels worth pausing with."

    core = _extract_core(reflection)
    low = (reflection_text or "").lower()

    if "steady" in low:
        return "There was a sense of steadiness."
    if "balanced" in low:
        return "There was a feeling of balance."
    if "calm" in low:
        return "There was a sense of calm present."

    core_clean = core.strip()
    low = core_clean.lower()

    if low.startswith(("it ", "there ", "was ", "were ")):
        mirror = core_clean.capitalize() + "."
    elif low.startswith("felt "):
        mirror = "Felt " + low[len("felt "):] + "."
    elif low.startswith("feel "):
        mirror = "Feeling " + low[len("feel "):] + "."
    else:
        prefix = PREFIXES[presence_stage % len(PREFIXES)]
        if low.endswith("ed today") or low.endswith("ed"):
            sense_text = low
            if sense_text.startswith("overwhelmed"):
                sense_text = sense_text.replace("overwhelmed", "overwhelm", 1)

            mirror = f"{prefix} a sense of {sense_text}."
        else:
            mirror = f"{prefix} {low}."

    mirror = _normalize(mirror)
    mirror = mirror.replace(" i ", " I ")
    mirror = mirror.replace(" i'", " I'")

    if mirror:
        mirror = mirror[0].upper() + mirror[1:]

    if len(mirror) > MAX_MIRROR_CHARS:
        mirror = mirror[:MAX_MIRROR_CHARS].rstrip(" ,;:-")
        if mirror[-1] not in ".!?":
            mirror += "."

    return mirror