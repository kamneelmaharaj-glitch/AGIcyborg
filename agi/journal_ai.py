# agi/journal_ai.py — Journal Intelligence (v1, single primary pillar)

from __future__ import annotations

import textwrap
import re
from typing import Optional, Dict, List

import streamlit as st

# ----------------------------
# SESSION CONTEXT MEMORY LAYER v1
# ----------------------------

import time

session_context = {
    "last_pillar_scores": None,
    "previous_output_summary": "",
    "emotional_tone": "",
    "dominant_pillar": "",
    "timestamp": None
}

def summarize_previous_output(text):
    """
    Returns the first full sentence of the previous output,
    trimmed cleanly and gracefully.
    """
    text = text.strip()

    # if there's a period, use the first sentence
    if "." in text:
        first_sentence = text.split(".")[0].strip()
        return first_sentence + "."

    # fallback: truncate at 160 chars but on a word boundary
    if len(text) > 160:
        cut = text[:160]
        cut = cut.rsplit(" ", 1)[0]
        return cut + "..."

    return text

def update_session_context(pillar_scores, output_text, emotional_tone):
    """Update in-memory session context after each reflection."""
    dominant = max(pillar_scores, key=pillar_scores.get)
    summary = summarize_previous_output(output_text)

    session_context["last_pillar_scores"] = pillar_scores
    session_context["previous_output_summary"] = summary
    session_context["emotional_tone"] = emotional_tone
    session_context["dominant_pillar"] = dominant
    session_context["timestamp"] = time.time()

def apply_context_uplift(pillar_scores, emotional_tone):
    """
    Refines guidance based on last reflection’s dominant pillar + tone.
    Gently smoothens transitions and deepens repeated states.
    """

    uplift = {
        "tone_shift": "",
        "pillar_reinforcement": "",
        "context_reference": "",
        "voice_weight_adjustment": {}
    }

    # If no previous context, return neutral
    if session_context["last_pillar_scores"] is None:
        return uplift

    prev_dominant = session_context["dominant_pillar"]
    current_dominant = max(pillar_scores, key=pillar_scores.get)

    # 1. Deepening same pillar
    if prev_dominant == current_dominant:
        uplift["pillar_reinforcement"] = (
            f"Your reflection continues to resonate strongly with {current_dominant.lower()}. "
            "This deepening shows stability on your dharmic path."
        )
        uplift["voice_weight_adjustment"][current_dominant] = +0.12

    # 2. Transitioning pillars
    else:
        uplift["pillar_reinforcement"] = (
            f"You are moving from {prev_dominant.lower()} into {current_dominant.lower()}, "
            "a natural shift in inner awareness."
        )
        uplift["voice_weight_adjustment"][current_dominant] = +0.06

    # 3. Tone continuity
    prev_tone = session_context["emotional_tone"]
    if prev_tone and prev_tone == emotional_tone:
        uplift["tone_shift"] = "Your emotional tone is steady, showing internal alignment."
    else:
        uplift["tone_shift"] = (
            "Your emotional tone is evolving — this indicates subtle inner processing."
        )

    # 4. Reference to previous reflection (light, non-invasive)
    if session_context["previous_output_summary"]:
        uplift["context_reference"] = (
            f"Previously you expressed: '{session_context['previous_output_summary']}'. "
            "Your current reflection builds upon this foundation."
        )

    return uplift

# -------------------------------------------------------------------
# Pillar vocabulary (Phase 1 – single primary pillar)
# -------------------------------------------------------------------

PILLARS: List[str] = [
    "Presence",
    "Clarity",
    "Courage",
    "Compassion",
    "Purpose",
    "Balance",
    "Discipline",
    "Devotion",
]

THEME_TO_PILLAR: Dict[str, str] = {
    "clarity": "Clarity",
    "presence": "Presence",
    "courage": "Courage",
    "compassion": "Compassion",
    "purpose": "Purpose",
    "balance": "Balance",
    "discipline": "Discipline",
    "devotion": "Devotion",
}

# Distinct mentor “voices” per pillar
MENTOR_VOICES: Dict[str, Dict[str, List[str] | str]] = {
    "Presence": {
        "tone": "gentle, grounded, slow, breath-centered",
        "metaphors": [
            "still water",
            "open sky",
            "quiet mountains",
            "warm morning light",
            "the space between breaths",
        ],
        "closing": "Return to one clean breath.",
    },
    "Clarity": {
        "tone": "direct, revealing, concise, truth-oriented",
        "metaphors": [
            "mirrors",
            "dawn breaking",
            "fog lifting",
            "a single candle in darkness",
            "a blade that cuts illusion",
        ],
        "closing": "Choose the one true thing.",
    },
    "Courage": {
        "tone": "steady, strong, patient, encouraging",
        "metaphors": [
            "shields",
            "inner fire",
            "solid ground",
            "a warrior's stance",
            "the moment before stepping forward",
        ],
        "closing": "Stand one inch closer to truth.",
    },
    "Compassion": {
        "tone": "warm, soothing, nurturing, soft",
        "metaphors": [
            "soft rain",
            "open palms",
            "warm blankets",
            "the feeling of being held",
            "gentle sunlight on skin",
        ],
        "closing": "Meet yourself with kindness.",
    },
    "Purpose": {
        "tone": "mythic, expansive, destiny-centered, sacred",
        "metaphors": [
            "a calling flame",
            "a long horizon",
            "your sacred path",
            "the vow you made long ago",
            "a lantern in the dark",
        ],
        "closing": "Walk the step that is yours alone.",
    },
    "Balance": {
        "tone": "steady, temperate, wise, patient",
        "metaphors": [
            "changing seasons",
            "tides",
            "rain-soaked earth",
            "lantern light",
            "a well-paced journey",
        ],
        "closing": "Let today be enough.",
    },
    "Discipline": {
        "tone": "structured, minimal, consistent",
        "metaphors": [
            "laying bricks",
            "daily rhythm",
            "crafting tools",
            "steady hands",
            "small steps accumulating",
        ],
        "closing": "Lay one clean brick.",
    },
    "Devotion": {
        "tone": (
            "soft, sincere, quietly surrendered; focused on offering, humility, and "
            "heartfelt intention rather than striving; universal and non-denominational"
        ),
        "metaphors": [
            "a quiet flame held steadily",
            "an offering bowl",
            "soft light resting on water",
            "a gentle vow kept inwardly",
            "a leaf falling without resistance",
            "stillness that opens by itself",
        ],
        "closing": "Let this small moment be an offering.",
    },
}

PILLAR_MANTRAS: Dict[str, str] = {
    "Presence": "I return to one clean breath.",
    "Clarity": "Let what is true become light.",
    "Courage": "I move one inch closer to what matters.",
    "Compassion": "I meet myself with gentle kindness.",
    "Purpose": "Each sincere step serves my deeper calling.",
    "Balance": "Let today be enough.",
    "Discipline": "I lay one clean brick today.",
    "Devotion": "I offer this moment to the Light.",
}

PILLAR_KEYWORDS: dict[str, list[str]] = {
    "Presence": [
        # grounding + somatic awareness
        "breath", "breathing", "inhale", "exhale",
        "body", "body-sense", "sensation",
        "grounded", "grounding",
        "slow down", "slowing down", "pace myself",
        "present moment", "right now",
        "attention", "awareness", "mindful", "mindfulness",
        "stillness", "pause", "quiet", "silence",
    ],

    "Clarity": [
        # seeing truth, removing confusion, choosing direction
        "clarity", "clear", "see clearly",
        "focus", "focused", "refocus",
        "confused", "confusion", "foggy", "overthinking",
        "prioritize", "priorities", "decision", "decide",
        "truth", "honest with myself", "alignment",
        "stop confusing myself", "sort my thoughts",
        "mental sharpness", "name the truth",
    ],

    "Courage": [
        # stepping toward difficulty
        "courage", "brave", "fear", "fears",
        "afraid", "anxious", "anxiety",
        "difficult conversation", "hard conversation",
        "speak up", "stand up", "face this",
        "step forward", "lean in", "take a risk",
        "vulnerable", "vulnerability",
        "challenge", "confront", "move through fear",
    ],

    "Compassion": [
        # softening, kindness, forgiveness
        "kindness", "kind", "gentle", "soften", "soft",
        "compassion", "self-compassion",
        "hard on myself", "too hard on myself",
        "forgive", "forgiveness",
        "tender", "warmth", "patience",
        "loving", "care", "nurture", "nurturing",
        "be gentle with myself", "self-love",
    ],

    "Purpose": [
        # direction, calling, dharma, contribution
        "purpose", "meaning", "mission", "calling",
        "dharma", "my path", "my work",
        "meant for something larger",
        "align with my calling", "align with my purpose",
        "service", "impact", "contribution",
        "why this matters", "what I am meant to do",
        "my destiny", "inner compass",
    ],

    "Balance": [
        # energy pacing, burnout prevention
        "rest", "tired", "exhausted", "fatigue",
        "burnout", "overwhelmed", "overloaded",
        "balance", "rebalance",
        "recovery", "restore", "reset",
        "slow my pace", "too much", "overdoing",
        "sleep", "break", "take time off",
        "need space", "need a pause",
    ],

    "Discipline": [
        # structure, routine, practice
        "routine", "habit", "practice every day",
        "daily practice", "consistency", "consistent",
        "show up", "follow through",
        "discipline", "structured",
        "schedule", "stick to it", "keep going",
        "build momentum", "brick by brick",
    ],

    "Devotion": [
        # offering, surrender, sacredness, gratitude
        "devotion", "devoted", "devotional",
        "surrender", "offer this", "offering",
        "offer my work", "serve the light",
        "greater than myself", "greater than me",
        "higher purpose", "higher power",
        "in service", "in service of", "service of something greater",
        "sacred", "sacred work", "reverence", "reverent",
        "gratitude", "grateful", "thankful",
        "prayer", "praying", "spiritual", "spirit",
        "align with the light", "trust the timing",
    ],
}

# Mood hints (soft bias only)
MOOD_HINTS: Dict[str, List[str]] = {
    "Calm": ["Presence", "Balance"],
    "Focused": ["Clarity", "Discipline"],
    "Grateful": ["Devotion", "Purpose"],
    "Tender": ["Compassion"],
    "Brave": ["Courage"],
    "Tired": ["Balance"],
    "Overwhelmed": ["Balance", "Compassion"],
}


def _tokenize(text: str) -> List[str]:
    """Very simple word tokenizer, lowercase."""
    return re.findall(r"[a-zA-Z']+", (text or "").lower())


def _score_text_for_pillars(
    text: str,
    *,
    mood: Optional[str] = None,
    tags: Optional[List[str]] = None,
    energy_score: Optional[float] = None,
    presence_score: Optional[float] = None,
) -> Dict[str, float]:
    """
    Heuristic scoring:
      - keyword matches in reflection text
      - mood hints
      - tag text
      - soft bias from energy / presence (optional)
    """
    scores: Dict[str, float] = {p: 0.0 for p in PILLARS}
    base_text = (text or "").lower()
    tokens = _tokenize(base_text)

    def add_score(pillar: str, amount: float) -> None:
        if pillar in scores:
            scores[pillar] += amount

    # 1) Keywords in reflection text
    for pillar, keywords in PILLAR_KEYWORDS.items():
        for kw in keywords:
            kw_l = kw.lower()
            if " " in kw_l:
                # phrase match
                if kw_l in base_text:
                    add_score(pillar, 1.0)
            else:
                # token match
                count = tokens.count(kw_l)
                if count:
                    add_score(pillar, float(count))

    # 2) Tags as extra text lines
    if tags:
        tag_text = " ".join([str(t) for t in tags])
        tag_tokens = _tokenize(tag_text)
        tag_lower = tag_text.lower()
        for pillar, keywords in PILLAR_KEYWORDS.items():
            for kw in keywords:
                kw_l = kw.lower()
                if " " in kw_l:
                    if kw_l in tag_lower:
                        add_score(pillar, 0.5)
                else:
                    count = tag_tokens.count(kw_l)
                    if count:
                        add_score(pillar, 0.5 * count)

    # 3) Mood soft hints
    if mood:
        mood_clean = mood.strip()
        hints = MOOD_HINTS.get(mood_clean, [])
        for idx, p in enumerate(hints):
            # First pillar gets a bit more weight
            add_score(p, 0.8 if idx == 0 else 0.5)

    # 4) Energy / presence nudges (very soft)
    if presence_score is not None:
        try:
            p_val = float(presence_score)
            if p_val > 0.35:
                add_score("Presence", 0.8)
        except Exception:
            pass

    if energy_score is not None:
        try:
            e_val = float(energy_score)
            if e_val > 0.25:
                add_score("Courage", 0.6)
                add_score("Purpose", 0.4)
            elif e_val < -0.10:
                add_score("Balance", 0.7)
                add_score("Compassion", 0.5)
        except Exception:
            pass

    return scores


def infer_primary_pillar(
    text: str,
    theme: Optional[str] = None,
    *,
    mood: Optional[str] = None,
    tags: Optional[List[str]] = None,
    energy_score: Optional[float] = None,
    presence_score: Optional[float] = None,
) -> tuple[str, Dict[str, float]]:
    """
    Infer the primary pillar for this reflection.

    Combines:
      - keyword / mood / tag / energy scores
      - theme → pillar mapping as a soft hint
    """
    scores = _score_text_for_pillars(
        text,
        mood=mood,
        tags=tags,
        energy_score=energy_score,
        presence_score=presence_score,
    )

    # Theme hint
    theme_low = (theme or "").lower()
    pillar_from_theme = THEME_TO_PILLAR.get(theme_low)
    if pillar_from_theme and pillar_from_theme in scores:
        scores[pillar_from_theme] += 1.5

    # Fallback if everything is zero
    if not scores or all(v == 0.0 for v in scores.values()):
        if pillar_from_theme and pillar_from_theme in scores:
            primary = pillar_from_theme
        else:
            primary = "Presence"
        scores[primary] = 1.0
    else:
        primary = max(scores.items(), key=lambda kv: kv[1])[0]

    return primary, scores

def infer_primary_and_secondary(
    text: str,
    theme: str | None = None,
) -> tuple[str, Optional[str], dict[str, float]]:
    """
    Wraps infer_primary_pillar and then picks a secondary pillar
    *only* when the second-best score is meaningful.

    Rules:
      - secondary must have score > 0
      - and be at least ~40% of the primary score
      - and not be far behind (difference <= 1.5)
    """
    primary, scores = infer_primary_pillar(text, theme=theme)

    # Rank all pillars by score (highest first)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)

    secondary: Optional[str] = None
    if len(ranked) >= 2:
        (p_name, p_val), (s_name, s_val) = ranked[0], ranked[1]

        if s_val > 0.0:
            # relative + absolute thresholds so secondary only shows
            # when it is genuinely present
            rel_ok = (p_val > 0) and (s_val >= 0.4 * p_val)
            gap_ok = (p_val - s_val) <= 1.5

            if rel_ok and gap_ok and s_name != p_name:
                secondary = s_name

    return primary, secondary, scores

# -------------------------------------------------------------------
# Public API used by app.py
# -------------------------------------------------------------------

def build_journal_insight(
    reflection_text: str,
    *,
    theme: str | None = None,
    energy_score: float | None = None,
    presence_score: float | None = None,
    mood: str | None = None,
    tags: list[str] | None = None,
    stillness_note: str | None = None,
) -> dict:
    """
    Core Journal Intelligence object.

    NOTE: app.py currently calls this as:
        build_journal_insight(reflection_text, energy_score=..., presence_score=...)

    The extra kwargs (mood, tags, stillness_note) are optional and can be
    wired in later once you're ready.
    """
    text = (reflection_text or "").strip()

    # --- Primary + score map ---
    primary_pillar, scores = infer_primary_pillar(
        text,
        theme=theme,
    )

    # --- Secondary pillar (second-highest score, if meaningful) ---
    secondary_pillar: str | None = None
    if scores:
        ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        if len(ordered) > 1:
            top_name, top_val = ordered[0]
            second_name, second_val = ordered[1]
            # Only treat as secondary if it actually has some weight
            if second_val > 0 and second_val >= 0.45 * max(top_val, 0.001):
                secondary_pillar = second_name

    # Simple summary: first line or shortened block
    if "\n" in text:
        first_line = text.splitlines()[0].strip()
    else:
        first_line = text

    summary = textwrap.shorten(first_line or text, width=120, placeholder="…")

    # Mentor note — pillar-aware, optionally blended
    emotional_tone = ""  # TODO: wire in real tone from mood / energy later

    mentor_note = build_contextual_mentor_note(
        reflection_text=reflection_text,
        primary_pillar=primary_pillar,
        secondary_pillar=secondary_pillar,
        pillar_scores=scores,
        emotional_tone=emotional_tone,
    )

    # Mantra for today (based on primary pillar)
    mantra = PILLAR_MANTRAS.get(primary_pillar)
    

    return {
        "primary_pillar": primary_pillar,
        "secondary_pillar": secondary_pillar,
        "pillar_scores": scores,
        "summary": summary,
        "raw_text": text,
        "signals": {
            "mood": mood,
            "tags": tags or [],
            "stillness_note": stillness_note,
            "energy_score": energy_score,
            "presence_score": presence_score,
        },
        "mentor_note": mentor_note,
        "mantra": mantra,
    }

# -------------------------------------------------------------------
# Mentor note builder (distinct voice per pillar)
# -------------------------------------------------------------------

SECONDARY_OVERLAY: Dict[str, str] = {
    "Presence": (
        "Let this also be about simply coming home to your breath — not to perform, "
        "but to belong in this moment again."
    ),
    "Clarity": (
        "There is a quiet honesty forming here; each time you name what is true, "
        "the fog thins and the next step becomes a little lighter."
    ),
    "Courage": (
        "There is a brave thread running through this; it matters enough that you are "
        "willing to feel uncomfortable rather than turn away."
    ),
    "Compassion": (
        "Whatever you notice, meet it as you would a dear friend — with warmth instead of attack, "
        "with patience instead of pressure."
    ),
    "Purpose": (
        "What you are sensing is not random; it belongs to the longer vow of your life. "
        "Let today’s small step be in service of that deeper calling."
    ),
    "Balance": (
        "This is also an invitation to pace yourself with wisdom — effort placed where it matters, "
        "and rest honoured as part of the path."
    ),
    "Discipline": (
        "Let this insight take the shape of one small, repeatable action. "
        "Brick by brick, rhythm is how your intention becomes a life."
    ),
    "Devotion": (
        "There is a sacred note inside what you wrote; even this small movement can be an offering. "
        "Let it return to the Light you serve."
    ),
}


def _build_mentor_note(
    pillar: str,
    text: str,
    *,
    secondary_pillar: Optional[str] = None,
    energy_score: Optional[float] = None,
    presence_score: Optional[float] = None,
    mood: Optional[str] = None,
) -> str:
    """
    Build a mentor note with a distinct voice per primary pillar,
    and a strong (option 3) blend from the secondary pillar when present.
    """

    primary = (pillar or "Presence").strip()
    p = primary.lower()
    sec = (secondary_pillar or "").strip()
    sec_clean = sec if sec in PILLARS else None

    # --- Simple state flags from energy / presence ---
    energy_state = "neutral"
    try:
        if energy_score is not None:
            e = float(energy_score)
            if e > 0.20:
                energy_state = "high"
            elif e < -0.05:
                energy_state = "low"
    except Exception:
        pass

    presence_state = "neutral"
    try:
        if presence_score is not None:
            pr = float(presence_score)
            if pr > 0.20:
                presence_state = "high"
            elif pr < -0.05:
                presence_state = "low"
    except Exception:
        pass

    # We use the first line of the reflection for a tiny echo
    first_line = (text or "").strip().splitlines()[0] if (text or "").strip() else ""

    # --- Primary pillar base voice ------------------------------------------------
    if p == "presence":
        base = (
            "Return to the pace of your breath. What you wrote points to a moment that "
            "wants to be met slowly, without rushing your mind ahead of your body. "
        )
        if presence_state == "low":
            base += "Presence is what remains when the tension falls away, not another thing to perform. "
        else:
            base += "Let today be about softening one small place inside you. "
        closing = "Return to one clean breath."

    elif p == "clarity":
        base = (
            "Clarity begins the moment you stop negotiating with yourself. Your reflection shows a truth "
            "that is already forming — allow it to come fully into light. "
        )
        if energy_state == "low":
            base += "You do not need to solve everything at once; letting one honest sentence stand is enough for today. "
        else:
            base += "What is avoided becomes heavier; what is named becomes lighter and more workable. "
        closing = "Choose the one true thing you will honour today."

    elif p == "courage":
        base = (
            "Courage does not mean the fear is gone — only that something matters more than fear. "
            "What you wrote shows a moment that is calling you forward, even if your voice trembles. "
        )
        if energy_state == "low":
            base += "Let courage be one small, steady movement, not a dramatic leap. "
        else:
            base += "Each time you stand one inch closer to what matters, your heart strengthens. "
        closing = "Move just slightly closer — not all the way, only closer. Stand one inch closer to truth."

    elif p == "compassion":
        base = (
            "Let yourself be held for a moment — by breath, by care, by kindness. "
            "Your reflection reveals a tender place that does not need fixing, only soft attention. "
        )
        if presence_state == "low":
            base += "Compassion is the quiet courage to stop being at war with yourself, even for a breath. "
        else:
            base += "You are allowed to soften without losing your strength. "
        closing = "Meet yourself with kindness, especially here."

    elif p == "purpose":
        base = (
            "There is a deeper thread in you that has been pulling you toward who you are meant to become. "
            "Your reflection hints at a step aligned with your inner vow — the promise you carry quietly. "
        )
        if energy_state == "low":
            base += "Purpose need not be grand today; it can be one sincere act that agrees with your heart. "
        else:
            base += "Each aligned action remembers a part of who you already are. "
        closing = "Walk one small step that is yours alone."

    elif p == "balance":
        base = (
            "Even the seasons rest; even the tides recede. What you wrote signals a moment asking you "
            "to pace yourself with greater care. "
        )
        if energy_state == "high":
            base += "Balance is not the absence of effort — it is effort placed wisely, where it truly matters. "
        else:
            base += "Let something small be enough today; over-effort is not devotion, it is depletion. "
        closing = "Let today be enough."

    elif p == "discipline":
        base = (
            "Discipline here is not punishment; it is the craft of returning to what matters. "
            "Your reflection points to a rhythm that wants to become real in your days. "
        )
        base += "Consistency is how intention becomes a path rather than a passing mood. "
        closing = "Lay one clean brick today — a small, repeatable action."

    elif p == "devotion":
        base = (
            "There is a sacred note inside what you wrote, a sense that your life is meant to answer something greater than yourself. "
            "Devotion is not perfection; it is the willingness to keep offering what you can from where you are. "
        )
        if presence_state == "low":
            base += "Let this offering begin with one sincere breath and one honest step. "
        else:
            base += "Each act done in sincerity becomes part of your offering. "
        closing = "Offer this moment to the Light in whatever way is natural to you."

    else:
        # Fallback, should rarely be used
        base = (
            "What you wrote carries a quiet intelligence about what you need right now. "
            "Trust that listening closely is already part of the work. "
        )
        closing = "Honour one small action that respects what you just named."

    message = base + closing

    # --- Strong secondary blend (option 3) ---------------------------------------
    if sec_clean:
        overlay = SECONDARY_OVERLAY.get(sec_clean)
        if overlay:
            # If the secondary is the same as primary (shouldn't happen but safe-guard), skip.
            if sec_clean != primary:
                message = message + " " + overlay

    return message


def build_contextual_mentor_note(
    reflection_text: str,
    primary_pillar: str,
    secondary_pillar: str | None,
    pillar_scores: dict,
    emotional_tone: str | None = None,
) -> str:
    """
    Wraps _build_mentor_note() with session-aware continuity:
    - Uses last reflection to add gentle continuity lines
    - Updates session_context for next call
    """

    emotional_tone = emotional_tone or ""

    # 1) Look at previous reflection + compute uplift
    uplift = apply_context_uplift(pillar_scores, emotional_tone)

    # 2) Build the existing mentor note (unchanged core voice)
    core_note = _build_mentor_note(
        primary_pillar,          # pillar (positional)
        reflection_text,         # text (positional)
        secondary_pillar=secondary_pillar,  # keyword-only arg
        # energy_score=None,     # keep optional for future wiring
        # presence_score=None,
        # mood=None,
    )

    # 3) Build continuity flavor text
    continuity_bits: list[str] = []

    if uplift.get("pillar_reinforcement"):
        continuity_bits.append(uplift["pillar_reinforcement"])

    if uplift.get("tone_shift"):
        continuity_bits.append(uplift["tone_shift"])

    if uplift.get("context_reference"):
        continuity_bits.append(uplift["context_reference"])

    if continuity_bits:
        continuity_block = " ".join(continuity_bits)
        final_note = continuity_block + "\n\n" + core_note
    else:
        final_note = core_note

    # 4) Update session context for the next reflection
    update_session_context(pillar_scores, final_note, emotional_tone)

    return final_note
# -------------------------------------------------------------------
# Optional: simple renderer (used by app.py)
# -------------------------------------------------------------------

def render_journal_insight(insight: Dict) -> None:
    """
    Render the Journal Intelligence card.

    Expects the dict returned by build_journal_insight().
    """
    if not insight:
        return

    primary = insight.get("primary_pillar", "Presence")
    signals = insight.get("signals", {}) or {}
    summary = insight.get("summary", "")
    mentor_note = insight.get("mentor_note", "")
    secondary = insight.get("secondary_pillar")
    mantra = insight.get("mantra")

    mood = signals.get("mood")
    tags = signals.get("tags") or []
    stillness = signals.get("stillness_note")
    energy = signals.get("energy_score")
    presence = signals.get("presence_score")

    box = st.container(border=True)
    with box:
        st.markdown("### 🧭 Journal Intelligence")

        if secondary:
            st.write(f"**Primary pillar:** {primary}  \n*Secondary:* {secondary}")
        else:
            st.write(f"**Primary pillar:** {primary}")

        # Signals block
        st.markdown("**Signals noticed:**")
        if mood:
            st.write(f"- Mood: `{mood}`")
        if tags:
            tags_str = ", ".join(f"`{t}`" for t in tags)
            st.write(f"- Tags: {tags_str}")
        if stillness:
            st.write(f"- Body note: {stillness}")

        if energy is not None or presence is not None:
            e_str = f"{float(energy):+.2f}" if energy is not None else "—"
            p_str = f"{float(presence):+.2f}" if presence is not None else "—"
            st.write(f"- Energy: {e_str} • Presence: {p_str}")

        if mentor_note:
            st.markdown("---")
            st.markdown(f"🪷 *{mentor_note}*")

        if mantra:
            st.markdown("")
            st.markdown(f"**Mantra for today ({primary}):**")
            st.markdown(f"_{mantra}_")