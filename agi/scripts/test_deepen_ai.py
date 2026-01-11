from __future__ import annotations

from textwrap import shorten
from datetime import datetime
import sys
import time
from agi.mood import detect_mood
import random
import os

TEST_MODE = os.getenv("DEEPEN_TEST_MODE") == "1"

from agi.deepen_ai import generate_deepen_insight, get_last_deepen_debug



def _banner(title: str) -> None:
    print("\n" + "=" * 90)
    print(title)
    print("=" * 90)


def _microstep_violations(step: str) -> list[str]:
    """Validate FINAL microstep only (raw model output is untrusted)."""
    s = (step or "").strip()
    low = s.lower()

    problems: list[str] = []
    if low.startswith("breathe"):
        problems.append("starts_with_breathe")
    if " and " in low:
        problems.append("contains_and")
    if "," in s:
        problems.append("contains_comma")

    return problems


def _print_case(i: int, case: dict) -> list[str]:
    theme = case["theme"]
    reflection = case["reflection"]
    note = case["note"]

    _banner(f"CASE {i}  |  Theme={theme}  |  NoteLen={len(note)}")
    print("Reflection tail:", (reflection.strip().splitlines()[-1] if reflection.strip() else "—"))
    print("Note preview   :", shorten(note.replace("\n", " "), width=120, placeholder="…"))
    print("-" * 90)

    if os.getenv("DEEPEN_NO_AI") == "1":
        stillness, insight, microstep = ("—", "", "")
        dbg = {}  # keep debug empty in no-ai mode
    else:
        stillness, insight, microstep = generate_deepen_insight(
            theme=theme,
            reflection_text=reflection,
            followup_note=note,
            recent_followups=case.get("recent_followups", []),
        )
        dbg = get_last_deepen_debug()

    try:
        assert_theme_signatures_non_corrective(dbg)
    except AssertionError as e:
        v.append(f"theme_signature_non_corrective:{e}")

    print("STILLNESS:", stillness)
    print("INSIGHT  :", insight)
    print("MICROSTEP:", microstep)
    

    # Validate FINAL microstep only
    violations = _microstep_violations(microstep)
    if violations:
        print("\n[FAIL] FINAL MICROSTEP VIOLATIONS:", ", ".join(violations))

    dbg = get_last_deepen_debug()
    print("\n[DEBUG]")
    keys = [
    "theme",
    "mood",
    "base_category",
    "biased_category",
    "chosen_category",
    "used_fallback",
    "shaped",
    "category_adjusted",
    "guardrail_adjusted",
    "model_error",
    "raw_model_microstep",
    "pre_category_microstep",
    "final_microstep",
]
    for k in keys:
        v = dbg.get(k)
        if isinstance(v, str) and len(v) > 140:
            v = shorten(v, width=140, placeholder="…")
        print(f"- {k}: {v}")

    return violations

print("DEEPEN_NO_AI =", os.getenv("DEEPEN_NO_AI"))

def main() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    base_reflection = f"""I slowed down today and noticed my mind trying to rush ahead of my body.
I want to stay honest and steady without forcing anything.
Timestamp: {now}
"""

    samples = {
        "soft": "I can slow down. It is okay to ease into today.",
        "clear": "I know what needs to be said. I will say it simply.",
        "focused": "Next I will write the one sentence. Then I will send it.",
        "tender": "I want to be kind to my heart right now. I will be gentle.",
        "heavy": "This feels hard. I am carrying a lot and it weighs on me.",
        "drained": "I feel tired. Empty. I don't have much left.",
        "overwhelmed": "It's too much, everything is piling up, I can't keep up, my mind won't stop...",
    }

    for k, txt in samples.items():
        print(k, "->", detect_mood(txt))
    print("-" * 90)

    cases = [
        # --- Presence ---
        dict(
            theme="Presence",
            reflection=base_reflection + "Tail: I can feel the tightness in my chest easing when I stop pushing.",
            note="I want to return to my body before I decide anything.",
            recent_followups=["I will slow down before reacting."],
        ),

        # --- Clarity ---
        dict(
            theme="Clarity",
            reflection=base_reflection + "Tail: The truth is I already know what needs to be said.",
            note="I keep circling the same thought because I’m avoiding one honest sentence.",
            recent_followups=["Name the truth simply.", "Don’t over-explain."],
        ),

        # --- Devotion (neutral, universal) ---
        dict(
            theme="Devotion",
            reflection=base_reflection + "Tail: I want my work to be an offering, not an ego project.",
            note="I want to show up with sincerity and humility today, quietly.",
            recent_followups=["Offer the work and let go of credit."],
        ),

        # --- Long note trigger (A.7 unsafe-length) ---
        dict(
            theme="Compassion",
            reflection=base_reflection + "Tail: I’ve been hard on myself and I feel tired.",
            note=("I notice I’ve been speaking to myself like I’m a problem to solve, "
                  "and it makes my chest feel tight and my shoulders rise. "
                  "I want to treat myself like someone I love, but I keep slipping into pressure, "
                  "perfectionism, and self-criticism, especially when I’m tired and trying to do too much."
                  " I just want one safe thing I can do right now."),
            recent_followups=["Be kinder in the moment."],
        ),

        # --- Keyword safety trigger (A.7) ---
        dict(
            theme="Balance",
            reflection=base_reflection + "Tail: I feel numb when I overload my day.",
            note="I feel numb and ashamed when I overload my day and then crash.",
            recent_followups=["Pace the day."],
        ),

        # --- Courage ---
        dict(
            theme="Courage",
            reflection=base_reflection + "Tail: I keep avoiding one small conversation.",
            note="I want to take one tiny brave step instead of rehearsing in my head.",
            recent_followups=["Do the smallest direct step."],
        ),

        # --- Discipline ---
        dict(
            theme="Discipline",
            reflection=base_reflection + "Tail: Consistency matters more than intensity for me right now.",
            note="I want one repeatable micro action I can do even when I’m tired.",
            recent_followups=["Small repeatable step."],
        ),

        # --- Purpose ---
        dict(
            theme="Purpose",
            reflection=base_reflection + "Tail: I want to align today’s work with what matters long-term.",
            note="I want to remember why I’m building this and act from that place.",
            recent_followups=["Serve the mission, not the mood."],
        ),

        # --- Surrender ---
        dict(
            theme="Surrender",
            reflection=base_reflection + "Tail: Some things are not mine to control.",
            note="I keep trying to control the outcome and it drains me.",
            recent_followups=["Release control gently."],
        ),

        # --- Calm-Sage ---
        dict(
            theme="Calm-Sage",
            reflection=base_reflection + "Tail: I can sense a quieter wisdom underneath the noise.",
            note="I want to listen to the quieter part of me before acting.",
            recent_followups=["Pause before acting."],
        ),
    ]
    
    
    THROTTLE_S = 5.0
    any_fail = False

    for i, case in enumerate(cases, start=1):
        violations = _print_case(i, case)
    if violations:
        any_fail = True
    time.sleep(THROTTLE_S + random.uniform(0, 0.3))

    _banner("DONE")

    if any_fail:
        print("FAIL: At least one FINAL MICROSTEP violated the rules (and/comma/Breathe).")
        sys.exit(1)
    else:
        print("PASS: All FINAL MICROSTEP outputs meet the rules.")
        sys.exit(0)


if __name__ == "__main__":
    main()