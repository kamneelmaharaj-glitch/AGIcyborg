# agi/threads/deepen_presence_thread.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Tuple

_PRESENCE_WORDS = (
    "body", "here", "now", "feel", "sense",
    "breath", "ground", "still", "quiet",
)

_DRIFT_WORDS = (
    "scattered", "distracted", "restless", "pulled", "tugged",
    "scroll", "doomscroll", "doom-scrolling",
    "switching", "tabs", "bouncing", "fragmented", "foggy",
    "avoid", "avoiding", "procrastin", "procrastinating",
    "can't focus", "cannot focus", "hard to focus",
)

_STABILITY_WORDS = (
    "steady", "balanced", "calm", "settled",
    "clear", "centered", "content", "stable",
    "grounded", "okay", "ok", "at ease",
)

# Presence stages (0-4)
# 0 Disconnection, 1 Return, 2 Steady, 3 Witness, 4 Abide
UPLIFT_MOODS = {"clear", "focused", "tender", "hopeful", "soft"}
HEAVY_MOODS  = {"heavy", "drained", "overwhelmed"}  # optional helper


def infer_presence_stage(
    *,
    reflection_text: str,
    mood: str,
    silenced: bool,
) -> Tuple[int, str]:
    """
    Presence Thread — Stage Inference (D-1)

    Returns:
        (stage: int 0–4, reason: str)

    Deterministic. Debug-only.
    """

    # Silence is stabilizing, not "abide"
    if silenced:
        return 2, "silence_gate"

    text = (reflection_text or "").lower().strip()
    if not text:
        return 1, "no_signal"

    hits = sum(1 for w in _PRESENCE_WORDS if w in text)
    drift = sum(1 for w in _DRIFT_WORDS if w in text)
    stability = sum(1 for w in _STABILITY_WORDS if w in text)

    # If drift is explicitly present, it should dominate a weak presence hit.
    # (This prevents "I’m distracted but I want to return to breath" from being misread as grounded.)
    if drift >= 2:
        return 1, f"drift_strong(drift={drift},presence={hits},len={len(text)})"

    if drift >= 1:
        # With drift present:
        # - strong presence can still count (hits>=3 -> witness)
        # - weak presence should not upgrade beyond "return"
        if hits >= 3:
            return 3, f"presence_with_drift(drift={drift},presence={hits},len={len(text)})"
        return 1, f"drift_day(drift={drift},presence={hits},len={len(text)})"

    # Reserve stage 4 for later (sequence-based); keep max at 3 for now
    if hits >= 4:
        return 3, f"embodied_presence_strong(hits={hits},len={len(text)})"

    if hits >= 3:
        return 3, f"embodied_presence(hits={hits},len={len(text)})"

    if hits >= 2:
        return 2, f"grounded_presence(hits={hits},len={len(text)})"
    
    if stability >= 2:
        return 2, f"stability_language_strong(stability={stability},presence={hits},len={len(text)})"

    if stability >= 1 and hits >= 1:
        return 2, f"stability_language(stability={stability},presence={hits},len={len(text)})"

    if stability >= 1 and drift == 0:
        return 2, f"steady_affect(stability={stability},presence={hits},len={len(text)})"

    return 0, f"fragmented_attention(hits={hits},len={len(text)})"


@dataclass(frozen=True)
class PresenceUpdateResult:
    stage_final: int
    drift_hits_new: int
    day: str
    dbg: Dict[str, object]


def _clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))


def update_presence_stage(
    *,
    stage_prev: int,
    stage_today: int,
    silenced: bool,
    mood: str,
    drift_hits_prev: int = 0,
    silence_reason: Optional[str] = None,
) -> PresenceUpdateResult:
    """
    D-2a rules (deterministic):
      - cap daily movement to +/-1
      - silence can stabilize but not advance (and should not accumulate drift)
      - progress up requires confirmation (anti-fluke)
      - decay is gentle: immediate -1 only on strong triggers; else 2-hit drift
    Returns:
      PresenceUpdateResult(stage_final, drift_hits_new, dbg)
    """

    # --- sanitize inputs ---
    stage_prev = _clamp(int(stage_prev or 0), 0, 4)
    stage_today = _clamp(int(stage_today or 0), 0, 4)
    drift_hits_prev = _clamp(int(drift_hits_prev or 0), 0, 2)

    mood_norm = (mood or "").strip().lower()
    silence_reason_norm = (silence_reason or "").strip().lower() or None

    dbg: Dict[str, object] = {
        "presence_stage_prev": stage_prev,
        "presence_stage_today": stage_today,
        "presence_drift_hits_prev": drift_hits_prev,
        "presence_silenced": bool(silenced),
        "presence_silence_reason": silence_reason_norm,
        "presence_mood": mood_norm,
    }

    # --- S1/S2: silence adjustment ---
    # Silence days do not "upgrade" stage; they can hold or (only) strong-decay.
    if silenced:
        stage_effective = min(stage_today, stage_prev)
        dbg["presence_stage_effective"] = stage_effective
        dbg["presence_rule_notes"] = "silence:min(today,prev)"
        # IMPORTANT: do not accumulate drift on silence days
        drift_hits_prev = 0
        dbg["presence_drift_hits_prev"] = drift_hits_prev
    else:
        stage_effective = stage_today
        dbg["presence_stage_effective"] = stage_effective
        dbg["presence_rule_notes"] = "normal"

    # --- P1: cap daily movement ---
    delta_raw = stage_effective - stage_prev
    delta_capped = _clamp(delta_raw, -1, +1)
    stage_candidate = _clamp(stage_prev + delta_capped, 0, 4)

    dbg["presence_delta_raw"] = delta_raw
    dbg["presence_delta_applied_cap"] = delta_capped
    dbg["presence_stage_candidate_preconfirm"] = stage_candidate

    # --- P2: progress confirmation (anti-fluke) ---
    progress_confirmed = True
    if stage_candidate == stage_prev + 1:
        # Default: not silenced AND not overwhelmed
        progress_confirmed = (not silenced) and (mood_norm != "overwhelmed")

        # Allow stable uplift for higher stages if mood supports it
        # BUT NEVER allow this to bypass silence
        if (not progress_confirmed) and (not silenced) and (stage_effective >= 3) and (mood_norm in UPLIFT_MOODS):
            progress_confirmed = True

        if not progress_confirmed:
            stage_candidate = stage_prev  # hold

    dbg["presence_progress_confirmed"] = bool(progress_confirmed)
    dbg["presence_stage_candidate"] = stage_candidate

    # --- Decay handling ---
    decay_mode = "none"
    drift_hits_new = drift_hits_prev
    stage_final = stage_candidate

    if stage_candidate == stage_prev - 1:
        # D2: strong decay triggers allow immediate -1 (no drift buffering)
        strong_decay = False

        # Strong decay ONLY for overwhelmed (drained should use drift buffering)
        if mood_norm in {"overwhelmed"} and stage_effective <= 1:
            strong_decay = True
            decay_mode = "strong:overwhelmed_low"

        if (not strong_decay) and silenced and (silence_reason_norm in {"emotional_overload", "overload"}):
            strong_decay = True
            decay_mode = "strong:silence_overload"

        # If not strong, D3: require 2 drift hits (but never on silenced days)
        if not strong_decay:
            if silenced:
                stage_final = stage_prev
                drift_hits_new = 0
                decay_mode = "silence:hold"
            else:
                drift_hits_new = _clamp(drift_hits_prev + 1, 0, 2)
                decay_mode = "drift"

                # Apply decay only on second hit
                if drift_hits_new >= 2:
                    stage_final = _clamp(stage_prev - 1, 0, 4)
                    drift_hits_new = 0  # reset after applying decay
                    decay_mode = "drift:applied"
                else:
                    stage_final = stage_prev  # hold stage on first drift hit
        else:
            stage_final = stage_candidate
            drift_hits_new = 0  # reset because we applied decisive decay

    else:
        # Not moving down
        # If stage_effective < stage_prev but we held due to anti-fluke logic,
        # we count drift gently — but only if not silenced.
        if stage_effective < stage_prev and (not silenced):
            drift_hits_new = _clamp(drift_hits_prev + 1, 0, 2)
            decay_mode = "drift(held)"

            if drift_hits_new >= 2:
                stage_final = _clamp(stage_prev - 1, 0, 4)
                drift_hits_new = 0
                decay_mode = "drift:applied_from_hold"
            else:
                stage_final = stage_candidate  # typically stage_prev
        else:
            stage_final = stage_candidate
            drift_hits_new = 0
            decay_mode = "none"

    dbg["presence_decay_mode"] = decay_mode
    dbg["presence_drift_hits_new"] = drift_hits_new
    dbg["presence_stage_final"] = stage_final

    from datetime import datetime, timezone
    day = datetime.now(timezone.utc).date().isoformat()

    return PresenceUpdateResult(
    stage_final=stage_final,
    drift_hits_new=drift_hits_new,
    day=day,
    dbg=dbg,
)


# Optional helper to map stage int to label (for UI/debug)
PRESENCE_STAGE_LABEL = {
    0: "disconnection",
    1: "return",
    2: "steady",
    3: "witness",
    4: "abide",
}

def presence_stage_label(stage: int) -> str:
    return PRESENCE_STAGE_LABEL.get(_clamp(int(stage or 0), 0, 4), "return")