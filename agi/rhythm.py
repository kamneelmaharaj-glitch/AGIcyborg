from __future__ import annotations

from typing import Literal, Optional

ResponseMode = Literal["normal", "gentle", "grounding"]


def infer_response_mode(
    *,
    presence_stage: Optional[int],
    drift_hits: int,
    silenced: bool,
    mood: Optional[str],
) -> ResponseMode:
    """
    Tiny Rhythm Intelligence seed.

    Returns a simple response mode that downstream surfaces
    can use to soften or intensify guidance.
    """

    mood_norm = (mood or "").strip().lower()

    # Silence should never increase intensity
    if silenced:
        return "gentle"

    # Repeated drift -> grounding first
    if drift_hits >= 2:
        return "grounding"

    # Early drift or fragile mood -> soften
    if drift_hits == 1:
        return "gentle"

    if mood_norm in {"tired", "overwhelmed", "drained", "restless"}:
        return "gentle"

    # Low presence can also benefit from gentleness
    if presence_stage is not None and int(presence_stage) <= 1:
        return "gentle"

    return "normal"