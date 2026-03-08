from typing import Literal, Optional

# --- Microstep preference by practice phase ---

def preferred_microstep_category(practice_phase: str | None) -> str | None:
    """
    Suggest a preferred microstep category based on Dharma phase.
    This is only a bias — microstep engine guardrails still apply.
    """

    mapping = {
        "stabilizing": "breath",     # breath-first regulation
        "steady": "posture",         # embodied awareness
        "deepening": "awareness",    # observation practices
        "recovering": "rest",        # minimal effort / silence
    }

    return mapping.get(practice_phase)

PracticePhase = Literal["stabilizing", "steady", "deepening", "recovering"]

def infer_practice_phase(
    *,
    presence_stage: Optional[int],
    drift_hits: int,
    silenced: bool,
    response_mode: str,
) -> PracticePhase:
    if silenced:
        return "recovering"
    if response_mode == "grounding":
        return "stabilizing"
    if response_mode == "gentle":
        return "stabilizing"
    if presence_stage is not None and int(presence_stage) >= 3 and drift_hits == 0:
        return "deepening"
    return "steady"

def preferred_microstep_category(practice_phase: str | None) -> str | None:
    mapping = {
        "stabilizing": "touch",   # body first
        "steady": "posture",
        "deepening": "breath",
        "recovering": "touch",
    }
    return mapping.get(practice_phase)