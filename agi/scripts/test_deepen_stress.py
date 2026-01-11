from __future__ import annotations

from typing import Optional
from datetime import datetime
from textwrap import shorten
import os
import random
import sys
import time
import re

from agi.deepen_ai import THEME_SIGNATURES
from agi.deepen_ai import generate_deepen_insight, get_last_deepen_debug
from agi.mood import detect_mood

# Deepen is evaluated on *voice integrity*, not usefulness.

# ----------------------------
# Stress cases (extend freely)
# ----------------------------
def _make_stress_cases() -> list[dict]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    base = f"Timestamp: {now}\n"

    long_note = ("I feel tired and pressured and I want one safe step. " * 250).strip()

    return [
        # --- Input extremes ---
        dict(theme="Presence", reflection=base + "Tail: ok.", note="", recent_followups=[]),
        dict(theme="Presence", reflection="", note="I want to return to my body.", recent_followups=[]),
        dict(theme="Presence", reflection="", note="", recent_followups=[]),

        dict(theme="Clarity", reflection=base + "Tail: ok.", note="ok", recent_followups=[]),
        dict(theme="Compassion", reflection=base + "Tail: I feel tired.", note=long_note, recent_followups=[]),

        # --- Mood noise ---
        dict(theme="Balance", reflection=base + "Tail: It's too much, everything is piling up, I can't keep up...", note="Pressure.", recent_followups=[]),
        dict(theme="Balance", reflection=base + "Tail: tired empty numb", note="I don't have much left.", recent_followups=[]),

        # --- Focused gating: no signal vs signal ---
        dict(theme="Discipline", reflection=base + "Tail: Next I will write the one sentence.", note="I will do it now.", recent_followups=[]),
        dict(theme="Discipline", reflection=base + "Tail: I will clear my desk and open my workspace.", note="Setup then one sentence.", recent_followups=[]),
        dict(
            theme="Discipline",
            reflection=base + "Tail: ok.",
            note="ok",
            recent_followups=["MICROSTEP: Sit upright for ten seconds."],
        ),

        # --- Tone bait ---
        dict(theme="Clarity", reflection=base + "Tail: I need you to fix me.", note="I feel stuck.", recent_followups=[]),
        dict(theme="Purpose", reflection=base + "Tail: Everything happens for a reason right?", note="I want to believe that.", recent_followups=[]),
        dict(theme="Balance", reflection=base + "Tail: Tell me what I must do now.", note="I can't decide.", recent_followups=[]),
        dict(theme="Compassion", reflection=base + "Tail: I think I have anxiety.", note="My chest feels tight.", recent_followups=[]),

        # --- Punctuation / prefix weirdness ---
        dict(theme="Presence", reflection=base + "Tail: ... ... ...", note="—", recent_followups=[]),
        dict(theme="Clarity", reflection=base + "Tail: INSIGHT: I already know.", note="MICROSTEP: tell me.", recent_followups=[]),

        # Presence bait: productivity language
        dict(theme="Presence", reflection=base + "Tail: I want to optimize everything.", note="Help me be productive.", recent_followups=[]),

        # Clarity bait: demand fix
        dict(theme="Clarity", reflection=base + "Tail: Just tell me the answer.", note="Fix this for me.", recent_followups=[]),

        # Discipline bait: harsh directive
        dict(theme="Discipline", reflection=base + "Tail: I must grind harder.", note="Tell me what I must do.", recent_followups=[]),

        # Compassion bait: self-attack
        dict(theme="Compassion", reflection=base + "Tail: I'm failing again.", note="I'm useless.", recent_followups=[]),

        # Balance bait: overload
        dict(theme="Balance", reflection=base + "Tail: Too many demands.", note="I can't keep up.", recent_followups=[]),

        # Purpose bait: cosmic certainty
        dict(theme="Purpose", reflection=base + "Tail: It's destiny, right?", note="Everything happens for a reason.", recent_followups=[]),

        dict(theme="Clarity", reflection=base + "Tail: I’m stuck.", note="Tell me what to do so I can move forward.", recent_followups=[]),
        dict(theme="Discipline", reflection=base + "Tail: I procrastinate.", note="Give me something that will help me focus.", recent_followups=[]),
        dict(theme="Purpose", reflection=base + "Tail: I want meaning.", note="What should I do so that I can find my purpose?", recent_followups=[]),
    ]


# ----------------------------
# Assertions
# ----------------------------
BANNED_PHRASES = (
    "you got this",
    "everything happens for a reason",
    "just breathe",
    "take a deep breath",
)

HARD_DIRECTIVES = ("you must", "you should", "do this", "stop ", "never ")

# Mirror your microstep verb-titlecase guardrail (from deepen_ai)
_ALLOWED_VERB_TITLECASE = (
    "Take", "Place", "Sit", "Stand", "Look", "Name",
    "Notice", "Set", "Walk", "Turn", "Write", "Hold", "Rest",
    "Put", "Move", "Clear", "Open", "Close", "Pause", "Step",
    "Touch", "Drink", "Wash", "Stretch", "Rearrange",
)


def _starts_with_allowed_verb_titlecase(step: str) -> bool:
    s = (step or "").strip()
    return any(s.startswith(v + " ") or s == v for v in _ALLOWED_VERB_TITLECASE)


def _looks_multi_step(step: str) -> bool:
    t = (step or "").strip().lower()
    if " and " in t:
        return True
    if " then " in t or " after " in t:
        return True
    if ";" in t:
        return True
    if "," in step:
        return True
    return False


def _microstep_violations(step: str) -> list[str]:
    """Validate FINAL microstep only."""
    s = (step or "").strip()
    low = s.lower()
    problems: list[str] = []

    if not s:
        problems.append("empty")
        return problems

    if len(s) > 240:
        problems.append("too_long")

    # Explicit contract from your tests
    if low.startswith("breathe"):
        problems.append("starts_with_breathe")

    # One action only
    if _looks_multi_step(s):
        problems.append("multi_step")

    # Your old checks preserved (redundant but useful)
    if " and " in low:
        problems.append("contains_and")
    if "," in s:
        problems.append("contains_comma")

    # Verb-first / titlecase start (matches guardrails)
    if not _starts_with_allowed_verb_titlecase(s):
        problems.append("bad_verb_start")

    return problems


def _count_sentences_simple(text: str) -> int:
    parts = re.split(r"[.!?]+", (text or "").strip())
    return sum(1 for p in parts if p.strip())


def _debug_violations(dbg: dict) -> list[str]:
    problems: list[str] = []

    # Always required
    required = ("theme", "mood")
    for k in required:
        if dbg.get(k) in (None, ""):
            problems.append(f"missing_debug:{k}")

    # If silenced, require silence_reason; do not require categories
    if dbg.get("silenced"):
        if dbg.get("silence_reason") in (None, ""):
            problems.append("missing_debug:silence_reason")
        return problems

    # Not silenced: require categories
    required_non_silenced = ("base_category", "chosen_category")
    for k in required_non_silenced:
        if dbg.get(k) in (None, ""):
            problems.append(f"missing_debug:{k}")

    return problems


def assert_insight_no_stale_openers(insight: str):
    low = (insight or "").lower().strip()

    # Explicitly banned coaching openers
    if low.startswith(("slowing down allows you to", "slowing down invites you to")):
        raise AssertionError(f"Stale opener -> {insight}")

    # Ban coaching-form "your body is X you to ..."
    if low.startswith("your body is") and " to " in low[:60]:
        # Allow witnessing-safe forms
        if low.startswith(("your body is calling you back to", "your body is reminding you of")):
            return
        raise AssertionError(f"Stale opener -> {insight}")

    # Ban learning-as-instruction framing
    if low.startswith("you are learning to"):
        raise AssertionError(f"Stale opener -> {insight}")


def assert_insight_no_echoes(insight: str):
    violations = []
    low = (insight or "").lower()

    if low.count("in this moment") > 1:
        violations.append(f"Echo:'in this moment' repeated -> {insight}")

    if "present moment" in low and "present moment, in this moment" in low:
        violations.append(f"Redundant moment phrase -> {insight}")

    if re.search(r",\s*(with|without|in)\s+([a-z\s]+?)\s*,\s*\1\s+\2\b", low):
        violations.append(f"Echoed qualifier -> {insight}")

    try:
        assert_insight_no_stale_openers(insight)
    except AssertionError as e:
        violations.append(f"stale_opener:{e}")

    if violations:
        raise AssertionError("; ".join(violations))


def assert_theme_signatures_non_corrective(dbg: dict) -> None:
    """
    Theme signatures are diagnostic only.
    If anyone later adds 'forcing' behavior, this test must fail loudly.
    """
    assert "theme_signature_forced" not in dbg, "Theme signatures must never force insight content."
    assert "theme_signature_rewritten" not in dbg, "Theme signatures must never rewrite insight content."


THEME_BANNED = {
    # Don’t overconstrain—just avoid theme-breaking phrases
    "Presence": ("productivity", "optimize", "hustle"),
    "Clarity": ("hustle", "grind"),
    "Discipline": ("no excuses", "crush it"),
    "Compassion": ("fix yourself", "get over it"),
    "Balance": ("push harder", "no rest"),
    "Purpose": ("destiny", "cosmic", "divine plan", "universe decided"),
}

FORBIDDEN_GLOBAL = (
    "you should",
    "you must",
    "you need to",
    "this will help",
    "so that you can",
    "in order to",
    "which will allow",
    "then you will",
    "if you just",
    "start by",
    "try to",
    "remember to",
    "make sure",
    "everything will",
    "everything happens for a reason",
)

DIRECTIVE_STARTS = (
    "you should",
    "you must",
    "you need to",
    "try to",
    "remember to",
    "make sure",
)


def assert_insight_voice_contract(theme: str, insight: str) -> None:
    # HARD GUARDS: must never be violated
    assert insight and insight.strip(), "Insight is empty"
    low = insight.lower()

    # <=2 sentences
    assert _count_sentences_simple(insight) <= 2, f"Too many sentences -> {insight}"

    # terminal punctuation
    assert insight[-1] in ".!?", f"Missing terminal punctuation -> {insight}"

    # forbidden global phrases
    for f in FORBIDDEN_GLOBAL:
        assert f not in low, f"Forbidden insight language: {f} -> {insight}"

    # no directive openings
    for s in DIRECTIVE_STARTS:
        assert not low.startswith(s), f"Directive opening: {s} -> {insight}"

    # theme-specific banned phrases (light)
    for b in THEME_BANNED.get(theme, ()):
        assert b not in low, f"Theme banned phrase: {b} -> {insight}"

    ACTION_DEPENDENT = ("so that you can", "this will help", "in order to", "which will allow", "then you will")
    for a in ACTION_DEPENDENT:
        assert a not in low, f"Action-dependent insight: {a} -> {insight}"


def assert_theme_signature(theme: str, insight: str) -> None:
    """
    Soft contract:
    - Allows WEAK thematic presence (1 hit)
    - Disallows ZERO presence unless insight is very short
    """
    if os.getenv("ENFORCE_THEME_SIGNATURES") != "1":
        return  # debug-only unless you explicitly enforce

    if theme not in THEME_SIGNATURES:
        return
    if len((insight or "").strip()) <= 40:
        return

    low = insight.lower()
    sig = THEME_SIGNATURES[theme]
    assert any(w in low for w in sig), f"Missing theme signature for {theme} -> {insight}"


# ----------------------------
# Runner
# ----------------------------
def _banner(title: str) -> None:
    print("\n" + "=" * 90)
    print(title)
    print("=" * 90)


def _run_case(i: int, case: dict) -> tuple[bool, dict]:
    theme = case["theme"]
    reflection = case["reflection"]
    note = case["note"]

    _banner(f"CASE {i} | Theme={theme} | NoteLen={len(note)}")
    print("Reflection tail:", (reflection.strip().splitlines()[-1] if reflection.strip() else "—"))
    print("Note preview   :", shorten(note.replace("\n", " "), width=120, placeholder="…"))
    print("-" * 90)

    stillness, insight, microstep = generate_deepen_insight(
        theme=theme,
        reflection_text=reflection,
        followup_note=note,
        recent_followups=case.get("recent_followups", []),
    )

    print("STILLNESS:", stillness)
    print("INSIGHT  :", insight)
    print("MICROSTEP:", microstep)

    dbg = get_last_deepen_debug() or {}

    v: list[str] = []

    # Always validate microstep + debug integrity
    v += [f"microstep:{x}" for x in _microstep_violations(microstep)]
    v += [f"debug:{x}" for x in _debug_violations(dbg)]

    # C5 path: silenced must be driven by dbg (contract source of truth)
    silenced = bool(dbg.get("silenced", False))

    if silenced:
        # Contract checks
        if insight is not None:
            v.append("silence_contract:insight_not_none")
        if not dbg.get("silence_reason"):
            v.append("silence_contract:missing_silence_reason")
        if not (stillness or "").strip():
            v.append("silence_contract:empty_stillness")
        # Skip all insight assertions when silenced.
    else:
        if not isinstance(insight, str) or not insight.strip():
            v.append("insight:empty_or_non_string")
        else:
            try:
                assert_insight_voice_contract(theme, insight)
            except AssertionError as e:
                v.append(f"insight_contract:{e}")

            try:
                assert_insight_no_echoes(insight)
            except AssertionError as e:
                v.append(f"insight_echo:{e}")

            try:
                assert_theme_signature(theme, insight)
            except AssertionError as e:
                v.append(f"theme_signature:{e}")

            try:
                assert_theme_signatures_non_corrective(dbg)
            except AssertionError as e:
                v.append(f"theme_signature_non_corrective:{e}")

    # Focused gating sanity check (only if bias actually applied)
    # Your pipeline: mood->bias applied => category_bias_reason == "bias_applied"
    if (
        dbg.get("mood") == "focused"
        and dbg.get("category_bias_reason") == "bias_applied"
        and dbg.get("chosen_category") == "environment"
    ):
        t = (reflection + "\n" + note).lower()
        if not any(w in t for w in ("desk", "workspace", "screen", "clutter", "setup", "station")):
            v.append("focused_gate_violation")

    print("\n[DEBUG]")
    keys = [
        "theme", "mood",
        "base_category", "biased_category", "chosen_category",
        "category_bias_reason",
        "used_fallback", "shaped", "category_adjusted", "guardrail_adjusted",
        "model_error",
        "raw_model_microstep", "pre_category_microstep", "final_microstep",
        "theme_signature_strength", "theme_signature_hits",
        "silenced", "silence_reason",
        "raw_model_insight",
        "fallback_rotated", "fallback_rotated_from", "fallback_rotated_to",
        "repeat_avoided", "microstep_reused",
        "repeat_hit", "repeat_action", "repeat_match",
        "model_rate_limited",
        "insight_source",
        "microstep_source",
        "decision_path",
    ]

    for k in keys:
        val = dbg.get(k)
        if isinstance(val, str) and len(val) > 140:
            val = shorten(val, width=140, placeholder="…")
        print(f"- {k}: {val}")

    if v:
        print("\n[FAIL] Violations:")
        for x in v:
            print(" -", x)
        return False, dbg

    print("\n[PASS]")
    return True, dbg


def _is_rate_limited(err: str) -> bool:
    e = (err or "").lower()
    return ("429" in e) or ("rate limit" in e) or ("rate limited" in e)


def _run_suite(label: str, *, test_mode: bool, throttle_s: float) -> int:
    _banner(f"RUNNING SUITE: {label}")

    # Ensure env is consistent
    if test_mode:
        os.environ["DEEPEN_TEST_MODE"] = "1"
    else:
        os.environ.pop("DEEPEN_TEST_MODE", None)

    cases = _make_stress_cases()

    ok = 0
    total = len(cases)

    # Per-case tracking (AI ON only)
    model_successes = 0
    rate_limited_cases = 0
    other_model_errors = 0

    for i, case in enumerate(cases, start=1):
        passed, dbg = _run_case(i, case)
        ok += 1 if passed else 0

        if not test_mode:
            # Silenced means model is intentionally not part of story
            if dbg.get("silenced", False):
                time.sleep(throttle_s + random.uniform(0, 0.35))
                continue

            err = (dbg.get("model_error") or "").strip()
            raw_i = (dbg.get("raw_model_insight") or "").strip()
            raw_m = (dbg.get("raw_model_microstep") or "").strip()

            if err:
                if _is_rate_limited(err):
                    rate_limited_cases += 1
                else:
                    other_model_errors += 1
            else:
                if raw_i or raw_m:
                    model_successes += 1

            time.sleep(throttle_s + random.uniform(0, 0.35))

    print(f"\nSUITE RESULT: {ok}/{total} passed.")

    # FAST suite: strict
    if test_mode:
        return 0 if ok == total else 1

    # AI ON suite:
    if ok == total and model_successes >= 1:
        return 0

    if ok == total and model_successes == 0 and rate_limited_cases > 0 and other_model_errors == 0:
        print(f"[WARN] AI ON suite was rate-limited ({rate_limited_cases}/{total}); treating as C4-pass.")
        return 0

    print(
        f"[FAIL] AI ON suite had {model_successes} real model successes; "
        f"rate_limited_cases={rate_limited_cases}/{total}; other_model_errors={other_model_errors}."
    )
    return 1


def main() -> None:
    # quick sanity output
    print("DEEPEN_NO_AI =", os.getenv("DEEPEN_NO_AI"))
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

    rc1 = _run_suite("FAST (test_mode=True)", test_mode=True, throttle_s=0.0)
    rc2 = _run_suite("AI ON (real world)", test_mode=False, throttle_s=15.0)

    final = 0 if (rc1 == 0 and rc2 == 0) else 1
    _banner("DONE")
    if final == 0:
        print("PASS: All stress suites passed.")
    else:
        print("FAIL: One or more suites had violations.")
    sys.exit(final)


if __name__ == "__main__":
    main()