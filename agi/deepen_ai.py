# agi/deepen_ai.py
from __future__ import annotations
from typing import List, Tuple, Optional
from agi.ai import ai_generate   # we reuse your existing OpenAI wrapper

SYSTEM_PRIMER = (
    "You are a compassionate mentor. Speak simply, concretely, and briefly. "
    "No psychoanalysis. Encourage grounded action aligned with inner calm."
)

def _compose_prompt(theme: str,
                    reflection_text: str,
                    followup_note: str,
                    recent_followups: Optional[List[str]] = None) -> str:
    history = " • ".join(recent_followups[-5:]) if recent_followups else "—"
    return (
        f"[SYSTEM]\n{SYSTEM_PRIMER}\n\n"
        f"[CONTEXT]\nTheme: {theme}\n"
        f"Reflection: {reflection_text.strip()}\n"
        f"Follow-up note: {followup_note.strip()}\n"
        f"Recent follow-ups: {history}\n\n"
        "[TASK]\n"
        "Return exactly two lines:\n"
        "INSIGHT: <one compassionate sentence that helps me understand my pattern>\n"
        "MICROSTEP: <one tiny, concrete step I can do in < 2 minutes>\n"
        "Keep it specific, non-judgmental, and calm."
    )

def generate_deepen_insight(theme: str,
                            reflection_text: str,
                            followup_note: str,
                            recent_followups: Optional[List[str]] = None
                            ) -> Tuple[str, str]:
    """
    Uses your ai_generate(theme, text) to produce:
      (insight, microstep)
    """
    prompt = _compose_prompt(theme, reflection_text, followup_note, recent_followups)
    # ai_generate returns (insight, mantra). We'll map its two lines to our two fields.
    raw_insight, raw_second = ai_generate(theme, prompt)

    # Normalize expected two-line format if the model already returned prefixes.
    def _strip_prefix(s: str) -> str:
        s = (s or "").strip()
        for p in ("INSIGHT:", "MICROSTEP:", "Insight:", "Microstep:"):
            if s.startswith(p):
                return s[len(p):].strip()
        return s

    insight = _strip_prefix(raw_insight)
    microstep = _strip_prefix(raw_second)
    return insight, microstep