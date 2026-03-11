# agi/mentor_tone.py — mentor tone selection


def infer_mentor_tone(
    presence_stage: int,
    recovery_mode: bool,
    practice_phase: str,
    rhythm_mode: str,
):
    """
    Determine mentor tone based on regulation state.
    """

    # Highest priority: recovery
    if recovery_mode:
        return "grounding"

    # Fragmented or low presence
    if presence_stage <= 1:
        return "gentle"

    # Deepening practice
    if practice_phase == "deepening":
        return "contemplative"

    # Default stable state
    return "reflective"