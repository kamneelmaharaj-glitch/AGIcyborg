from typing import Literal, Optional

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