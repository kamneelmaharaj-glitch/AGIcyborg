# agi/ai.py
from __future__ import annotations
import json, re, textwrap
from typing import Tuple, Optional, Dict
import streamlit as st

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None

from .config import OPENAI_API_KEY, OPENAI_PROJECT
from .themes import THEME_PROFILES

def _get_openai_client() -> Optional[OpenAI]:
    if not (OPENAI_API_KEY and OpenAI):
        return None
    if OPENAI_API_KEY.startswith("sk-proj-"):
        if not (OPENAI_PROJECT and OPENAI_PROJECT.startswith("proj_")):
            return None
        return OpenAI(api_key=OPENAI_API_KEY, project=OPENAI_PROJECT)
    return OpenAI(api_key=OPENAI_API_KEY)

def _build_messages(theme: str, reflection: str) -> list:
    profile = THEME_PROFILES.get(theme, THEME_PROFILES["Clarity"])
    system = f"""
You are an Awakened Mentor for the theme "{theme}".
Persona: {profile['persona']}
Voice: {profile['voice']}
Boundaries:
- You are not a medical, legal, or crisis service; avoid clinical/diagnostic claims.
- Stay supportive and practical; do not mention being an AI.
- Use simple, grounded language; avoid clichés and spiritual bypassing.
Task:
1) Offer ONE short, practical INSIGHT (<= {profile['max_words']} words) tailored to the reflection.
2) Offer ONE MANTRA (<= 10 words) aligned with: {profile['mantra_hint']}

Return ONLY valid JSON:
{{"insight":"...", "mantra":"..."}}
"""
    user = f"""
Reflection:
{reflection.strip()}

Constraints:
- Keep the insight concrete and kind.
- Keep the mantra present-tense, breath-friendly.
- Avoid quoting the reflection; respond to it.
- No emojis.
"""
    return [
        {"role": "system", "content": textwrap.dedent(system).strip()},
        {"role": "user", "content": textwrap.dedent(user).strip()},
    ]

def _clean_json(s: str) -> Dict[str,str]:
    try:
        return json.loads(s)
    except Exception:
        m = re.search(r"\{.*\}", s, flags=re.S)
        if m:
            try: return json.loads(m.group(0))
            except Exception: pass
    return {"insight":"","mantra":""}

def ai_generate(theme: str, reflection: str) -> Tuple[str, str]:
    client = _get_openai_client()
    if not client:
        raise RuntimeError("AI disabled or not configured.")
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=_build_messages(theme, reflection),
        temperature=0.4,
        max_tokens=280,
        response_format={"type": "json_object"},
    )
    raw = (resp.choices[0].message.content or "{}").strip()
    data = _clean_json(raw)
    insight = (data.get("insight") or "").strip()
    mantra  = (data.get("mantra")  or "").strip()
    if len(insight) > 400: insight = insight[:400].rsplit(" ", 1)[0] + "…"
    if len(mantra.split()) > 10: mantra = " ".join(mantra.split()[:10])
    return insight, mantra