from __future__ import annotations

import re

MAX_MIRROR_CHARS = 140

PREFIXES = (
    "You noticed",
    "You noticed",
    "There was a sense",
    "You noticed",
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _extract_core(reflection: str) -> str:
    if not reflection:
        return ""

    parts = re.split(r"[.!?]", reflection)
    core = parts[0].strip()

    core = re.sub(
        r"^(i feel|i felt|i noticed|i think|today|i)\s+",
        "",
        core,
        flags=re.I,
    )

    return core


def _to_second_person(text: str) -> str:
    text = re.sub(r"^my\b", "your", text, flags=re.I)
    text = re.sub(r"\bmy\b", "your", text, flags=re.I)
    text = re.sub(r"\bme\b", "you", text, flags=re.I)
    return text


def generate_mirror(reflection_text: str, mood: str, presence_stage: int) -> str:
    reflection = _normalize(reflection_text)
    if not reflection:
        return "Something here feels worth pausing with."

    core = _extract_core(reflection)
    reflection_low = reflection.lower()
    core_clean = core.strip()
    low = core_clean.lower()

    # ------------------------------------------------------------------
    # Stable direct mappings (keep these first)
    # ------------------------------------------------------------------
    if "steady" in reflection_low:
        return "There was a sense of steadiness."
    if "balanced" in reflection_low:
        return "There was a feeling of balance."
    if "calm" in reflection_low:
        return "There was a sense of calm present."

    # ------------------------------------------------------------------
    # Semantic mappings for common emotional / situational states
    # ------------------------------------------------------------------
    
    if re.search(r"\b(it's|its|it is)\s+an?\s+overwhelming\b", reflection_low):
        return "There is an overwhelming feeling today." if "today" in reflection_low else "There is an overwhelming feeling."
    
    if "overwhelmed" in reflection_low:
        return "You noticed a sense of overwhelm today." if "today" in reflection_low else "You noticed a sense of overwhelm."

    if re.search(r"\bhurt\b", reflection_low):
        return "There was a sense of hurt."
    
    if re.search(r"\bavoiding\b|\bavoid\b", reflection_low):
        return "There was a sense of avoidance."
    
    if (
        "can't control" in reflection_low
        or "can’t control" in reflection_low
        or "cannot control" in reflection_low
    ):
        return "You noticed a sense of lack of control."

    # ------------------------------------------------------------------
    # Semantic noun-form mappings for cleaner mirror language
    # ------------------------------------------------------------------
    NOUN_MAP = {
        "heavy": "heaviness",
        "tight": "tightness",
        "uncertain": "uncertainty",
        "distracted": "distraction",
        "tired": "tiredness",
        "frustrated": "frustration",
    }

    for word, noun in NOUN_MAP.items():
        if re.search(rf"\b{word}\b", reflection_low):
            if "today" in reflection_low:
                return f"You noticed a sense of {noun} today."
            return f"You noticed a sense of {noun}."

    # ------------------------------------------------------------------
    # Direct ownership-preserving handling
    # ------------------------------------------------------------------
    if low.startswith("my "):
        natural = _to_second_person(core_clean)
        mirror = f"You noticed {natural}."

    # ------------------------------------------------------------------
    # Natural sentence handling
    # ------------------------------------------------------------------
    elif low.startswith(("it ", "there ", "was ", "were ")):
        mirror = core_clean.capitalize() + "."
    elif low.startswith("felt "):
        mirror = "Felt " + low[len("felt "):] + "."
    elif low.startswith("feel "):
        mirror = "Feeling " + low[len("feel "):] + "."
    elif low.startswith(("can ", "could ", "should ", "would ")):
        mirror = f"You {low}."
    else:
        prefix = PREFIXES[presence_stage % len(PREFIXES)]

        if low.endswith("ed today") or low.endswith("ed"):
            sense_text = low
            if sense_text.startswith("overwhelmed"):
                sense_text = sense_text.replace("overwhelmed", "overwhelm", 1)

            mirror = f"{prefix} a sense of {sense_text}."
        else:
            mirror = f"{prefix} {low}."

    mirror = _normalize_mirror_pronouns(mirror)
    mirror = _normalize(mirror)
    mirror = mirror.replace(" i ", " I ")
    mirror = mirror.replace(" i'", " I'")

    mirror = _clean_mirror_sentence(mirror)

    if mirror:
        mirror = mirror[0].upper() + mirror[1:]

    if len(mirror) > MAX_MIRROR_CHARS:
        mirror = mirror[:MAX_MIRROR_CHARS].rstrip(" ,;:-")
        if mirror and mirror[-1] not in ".!?":
            mirror += "."

    return mirror

def _dedupe_redundant_phrases(text: str) -> str:
    import re

    t = text

    # Remove stacked meaning overlaps
    t = re.sub(r"\bstill feel the same\b", "still feel", t)
    t = re.sub(r"\bthe same .* again today\b", "the same today", t)
    t = re.sub(r"\bagain today\b", "today", t)

    # Remove accidental repeats
    t = re.sub(r"\b(still|same|again)\s+\1\b", r"\1", t)

    return t


def _normalize_mirror_pronouns(text: str) -> str:
    t = (text or "").strip()

    # sentence starts
    t = re.sub(r"^(I|i)\b", "you", t)
    t = re.sub(r"^(I'm|i'm)\b", "you're", t)
    t = re.sub(r"^(I’ve|i’ve|I've|i've)\b", "you've", t)

    # anywhere in sentence
    t = re.sub(r"\b(I am|i am)\b", "you are", t)
    t = re.sub(r"\b(I'm|i'm)\b", "you're", t)
    t = re.sub(r"\b(I was|i was)\b", "you were", t)
    t = re.sub(r"\b(I feel|i feel)\b", "you feel", t)
    t = re.sub(r"\b(I felt|i felt)\b", "you felt", t)
    t = re.sub(r"\b(I have|i have)\b", "you have", t)
    t = re.sub(r"\b(I\b|i\b)", "you", t)

    t = re.sub(r"\b(my|My)\b", "your", t)
    t = re.sub(r"\b(me|Me)\b", "you", t)

    return t


def _clean_mirror_sentence(text: str) -> str:
    t = (text or "").strip()

    t = t.replace("sense still feel", "sense that you still feel")
    t = t.replace("sense still feels", "sense that still feels")
    t = t.replace("There was a sense that you still feel", "You still feel")
    t = t.replace("There was a sense still feel", "You still feel")

    # Naturalize adjective-state mirrors
    t = re.sub(
        r"\bYou noticed relaxed\b",
        "You noticed a sense of relaxation",
        t,
    )

    t = t.replace(" in spa", " in the spa")

    t = _dedupe_redundant_phrases(t)

    if t and not t[0].isupper():
        t = t[0].upper() + t[1:]

    if t and t[-1] not in ".!?":
        t += "."

    return t

def _normalize_ai_sentence(text: str) -> str:
    t = (text or "").strip()

    # Fix common missing structure
    t = re.sub(r"\bnoticed (\w+ed)\b", r"noticed a sense of \1", t)

    # Fix "relaxed", "tired", etc → feeling form
    t = re.sub(r"\bnoticed a sense of (relaxed|tired|focused|calm)\b",
               r"noticed a sense of \1", t)

    # Optional refinement for better tone
    t = t.replace("in spa", "in the spa")

    # Capitalize + punctuation
    if t and not t[0].isupper():
        t = t[0].upper() + t[1:]

    if t and t[-1] not in ".!?":
        t += "."

    return t