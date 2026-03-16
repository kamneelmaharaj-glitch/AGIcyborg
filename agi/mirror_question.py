from __future__ import annotations

import re

MAX_QUESTION_CHARS = 120


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def generate_mirror_question(
    reflection_text: str,
    mood: str,
    presence_stage: int,
) -> str:
    """
    Generate a gentle reflective question.
    Deterministic and intentionally simple.
    """

    reflection = (reflection_text or "").lower()

    # Stable states
    if "steady" in reflection or "steadiness" in reflection:
        q = "What seemed to support that steadiness today?"

    elif "balanced" in reflection or "balance" in reflection:
        q = "What helped that sense of balance appear?"

    elif "calm" in reflection:
        q = "What may have contributed to that calm?"

    # Drift states
    elif "distracted" in reflection or "scattered" in reflection:
        q = "What helped you notice that drift?"

    elif "overwhelmed" in reflection:
        q = "What felt most present within that overwhelm?"

    # Default gentle reflection
    else:
        q = "What felt most noticeable in that moment?"

    q = _normalize(q)

    if len(q) > MAX_QUESTION_CHARS:
        q = q[:MAX_QUESTION_CHARS].rstrip(" ,;:-")
        if not q.endswith("?"):
            q += "?"

    return q