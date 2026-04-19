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
    Deterministic, simple, and context-aware (no interpretation).
    """

    reflection = (reflection_text or "").lower()

    # ----------------------------
    # Stable states (unchanged)
    # ----------------------------
    if "steady" in reflection or "steadiness" in reflection:
        q = "What seemed to support that steadiness today?"

    elif "balanced" in reflection or "balance" in reflection:
        q = "What helped that sense of balance appear?"

    elif "calm" in reflection:
        q = "What may have contributed to that calm?"

    # ----------------------------
    # Drift / signal states
    # ----------------------------
    elif "distracted" in reflection or "scattered" in reflection:
        q = "What helped you notice that drift?"

    elif "overwhelmed" in reflection:
        q = "What feels a little clearer within that overwhelm?"

    # ----------------------------
    # Subtle pattern-aware refinement (NEW)
    # ----------------------------
    else:
        repeat_signals = ("again", "still", "same", "keep", "kept")
        capacity_signals = ("tired", "heavy", "drained", "exhausted")
        overwhelm_signals = ("too much", "a lot", "everything")
        uncertainty_signals = ("uncertain", "unclear", "foggy", "confused")

        if any(x in reflection for x in repeat_signals):
            q = "What feels even slightly different this time?"

        elif any(x in reflection for x in capacity_signals):
            q = "What feels a little more within reach right now?"

        elif any(x in reflection for x in overwhelm_signals):
            q = "What feels a little less crowded right now?"

        elif any(x in reflection for x in uncertainty_signals):
            q = "What feels a little more known right now?"

        else:
            q = "What feels a little clearer now?"

    # ----------------------------
    # Normalize + safety
    # ----------------------------
    q = _normalize(q)

    if len(q) > MAX_QUESTION_CHARS:
        q = q[:MAX_QUESTION_CHARS].rstrip(" ,;:-")
        if not q.endswith("?"):
            q += "?"

    return q