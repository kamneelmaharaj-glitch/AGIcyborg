# agi/recovery.py — recovery mode inference

from __future__ import annotations
from typing import Dict


def infer_recovery_mode(
    presence_stage: int,
    drift_total: int,
) -> Dict:
    """
    Determine whether the system should enter recovery mode.

    Recovery mode activates when accumulated drift reaches a threshold.
    """

    recovery_mode = False
    reason = None

    if drift_total >= 2:
        recovery_mode = True
        reason = "drift_threshold"

    return {
        "recovery_mode": recovery_mode,
        "presence_stage": presence_stage,
        "drift_total": drift_total,
        "reason": reason,
    }