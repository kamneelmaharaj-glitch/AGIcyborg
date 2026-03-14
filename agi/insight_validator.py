from __future__ import annotations

import re


MAX_INSIGHT_CHARS = 220

FORBIDDEN_PHRASES = {
    "you should",
    "you must",
    "you need to",
    "do this now",
    "immediately",
    "make sure",
    "don't forget",
    "remember to",
}

TONE_PREFIX = {
    "grounding": "Return to what is here.",
    "gentle": "Something softer may already be present.",
    "reflective": "What feels true may already be near.",
    "contemplative": "A quieter meaning may already be forming.",
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _has_forbidden_language(text: str) -> bool:
    low = (text or "").lower()
    return any(p in low for p in FORBIDDEN_PHRASES)


def _looks_over_directive(text: str) -> bool:
    low = (text or "").lower()

    # crude but useful: too many imperative-feeling starts
    directive_starts = (
        "pause ",
        "take ",
        "sit ",
        "stand ",
        "place ",
        "write ",
        "look ",
        "notice ",
        "set ",
        "name ",
    )
    return any(low.startswith(x) for x in directive_starts)


def validate_insight(text: str, tone: str) -> str:
    """
    Validate and normalize a generated insight.
    Falls back to a tone-aligned safe insight when needed.
    """

    insight = _normalize(text)

    if not insight:
        return TONE_PREFIX.get(tone, TONE_PREFIX["reflective"])

    # limit length
    if len(insight) > MAX_INSIGHT_CHARS:
        insight = insight[:MAX_INSIGHT_CHARS].rstrip(" ,;:-")
        if insight and insight[-1] not in ".!?":
            insight += "."

    # reject if too directive
    if _has_forbidden_language(insight) or _looks_over_directive(insight):
        return TONE_PREFIX.get(tone, TONE_PREFIX["reflective"])

    # keep to one compact reflection
    if insight.count(".") > 2:
        parts = [p.strip() for p in insight.split(".") if p.strip()]
        insight = ". ".join(parts[:2]).strip()
        if insight and insight[-1] not in ".!?":
            insight += "."

    return insight