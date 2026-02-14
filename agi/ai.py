# agi/ai.py
from __future__ import annotations

import json
import re
import textwrap
from typing import Tuple, Optional, Dict
import streamlit as st  # noqa: F401  (kept in case you use it elsewhere)
import time
import random
import os

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None

from .config import OPENAI_API_KEY, OPENAI_PROJECT
from .themes import THEME_PROFILES


# ---------------------------------------------------------------------------
# OpenAI client
# ---------------------------------------------------------------------------

def _get_openai_client() -> Optional[OpenAI]:
    if not (OPENAI_API_KEY and OpenAI):
        return None
    if OPENAI_API_KEY.startswith("sk-proj-"):
        if not (OPENAI_PROJECT and OPENAI_PROJECT.startswith("proj_")):
            return None
        return OpenAI(api_key=OPENAI_API_KEY, project=OPENAI_PROJECT)
    return OpenAI(api_key=OPENAI_API_KEY)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sleep_with_backoff(attempt: int, base: float = 0.6, cap: float = 12.0) -> float:
    """
    Exponential backoff with jitter.
    attempt starts at 1.
    """
    delay = min(cap, base * (2 ** (attempt - 1)))
    delay = delay * random.uniform(0.7, 1.3)  # jitter: 70%..130%
    time.sleep(delay)
    return delay


def _clean_json(s: str) -> Dict[str, str]:
    try:
        return json.loads(s)
    except Exception:
        m = re.search(r"\{.*\}", s, flags=re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {"insight": "", "mantra": ""}


def _extract_retry_after_seconds(err: Exception) -> Optional[float]:
    """
    Best-effort: if the OpenAI SDK error exposes a Retry-After header, honor it.
    If we can't find it, return None.
    """
    try:
        headers = None

        # common patterns
        if hasattr(err, "response") and getattr(err, "response") is not None:
            resp = getattr(err, "response")
            if hasattr(resp, "headers"):
                headers = resp.headers

        if headers is None and hasattr(err, "headers"):
            headers = getattr(err, "headers")

        if headers:
            ra = headers.get("retry-after") or headers.get("Retry-After")
            if ra:
                return float(ra)
    except Exception:
        return None

    return None


def _is_rate_limited_error(e: Exception) -> bool:
    msg = str(e).lower()
    return ("429" in msg) or ("rate limit" in msg) or ("rate limited" in msg)


def _is_5xx_error(e: Exception) -> bool:
    msg = str(e)
    return any(code in msg for code in ("Error code: 500", "Error code: 502", "Error code: 503", "Error code: 504"))

def _is_insufficient_quota(e: Exception) -> bool:
    msg = str(e).lower()
    return ("insufficient_quota" in msg) or ("exceeded your current quota" in msg)

# ---------------------------------------------------------------------------
# Standard AI generator (insight + mantra) — unchanged behavior
# ---------------------------------------------------------------------------

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
    mantra = (data.get("mantra") or "").strip()
    if len(insight) > 400:
        insight = insight[:400].rsplit(" ", 1)[0] + "…"
    if len(mantra.split()) > 10:
        mantra = " ".join(mantra.split()[:10])
    return insight, mantra


# ---------------------------------------------------------------------------
# Deepen rate-limit circuit breaker
# ---------------------------------------------------------------------------

_DEEPEN_RATE_LIMIT_UNTIL: float = 0.0  # epoch seconds


def _deepen_in_cooldown() -> bool:
    return time.time() < _DEEPEN_RATE_LIMIT_UNTIL


def _set_deepen_cooldown(seconds: float) -> None:
    global _DEEPEN_RATE_LIMIT_UNTIL
    _DEEPEN_RATE_LIMIT_UNTIL = max(_DEEPEN_RATE_LIMIT_UNTIL, time.time() + max(0.0, seconds))


# ---------------------------------------------------------------------------
# Deepen-only generator (insight + microstep)
# ---------------------------------------------------------------------------

def ai_generate_deepen(theme: str, prompt: str) -> Tuple[str, str]:
    """
    Deepen-only generator.
    Returns: (insight_line, microstep_line)

    Behavior:
    - Circuit breaker: if we recently got 429, fail fast until cooldown expires.
    - Retries ONLY on 429 + 5xx with exponential backoff + jitter.
    - Honors Retry-After if available on 429.
    """

    client = _get_openai_client()
    if not client:
        raise RuntimeError("AI disabled or not configured.")

    if _deepen_in_cooldown():
        raise RuntimeError("Rate limited (deepen cooldown active).")

    # knobs (safe defaults)
    max_retries = int(os.getenv("DEEPEN_AI_MAX_RETRIES", "4"))          # total attempts = 1 + max_retries
    base_backoff = float(os.getenv("DEEPEN_AI_RETRY_BASE_S", "0.8"))
    cap_backoff = float(os.getenv("DEEPEN_AI_RETRY_CAP_S", "8.0"))
    default_429_cooldown = float(os.getenv("DEEPEN_AI_429_COOLDOWN_S", "30.0"))

    last_err: Exception | None = None

    for attempt in range(0, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Output exactly two lines: INSIGHT: ... and MICROSTEP: ... . No other text."},
                    {"role": "user", "content": (prompt or "").strip()},
                ],
                temperature=0.3,
                max_tokens=160,
                stop=["\n\n"],
            )

            text = (resp.choices[0].message.content or "").strip()
            raw_lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

            def _clean_line(ln: str) -> str:
                ln = ln.strip()
                ln = ln.lstrip("-•* \t")
                if len(ln) >= 3 and ln[0].isdigit() and ln[1] in [")", "."] and ln[2] == " ":
                    ln = ln[3:].strip()
                return ln

            lines = [_clean_line(ln) for ln in raw_lines if _clean_line(ln)]

            insight = ""
            micro = ""

            for ln in lines:
                low = ln.lower()
                if low.startswith("insight:"):
                    insight = ln.split(":", 1)[1].strip()
                elif low.startswith("microstep:"):
                    micro = ln.split(":", 1)[1].strip()

            # fallback: first two lines
            if not insight and lines:
                insight = lines[0].replace("INSIGHT:", "").replace("Insight:", "").strip()
            if not micro and len(lines) > 1:
                micro = lines[1].replace("MICROSTEP:", "").replace("Microstep:", "").strip()

            # clamp to single line each
            insight = (insight.splitlines()[0] if insight else "").strip()
            micro = (micro.splitlines()[0] if micro else "").strip()
            return insight, micro

        except Exception as e:
            last_err = e

            is_429 = _is_rate_limited_error(e)
            is_5xx = _is_5xx_error(e)
            is_quota = _is_insufficient_quota(e)

            # 429 => set circuit breaker
            if is_429:
                retry_after = _extract_retry_after_seconds(e)
                _set_deepen_cooldown(retry_after if retry_after is not None else default_429_cooldown)

            # retry only on 429 + 5xx
            # Do NOT retry quota problems (they won't resolve with backoff)
            should_retry = (is_429 or is_5xx) and (not is_quota)

            if (not should_retry) or (attempt >= max_retries):
            # Surface a clear marker for callers
                if is_quota:
                    raise RuntimeError("AI_UNAVAILABLE:insufficient_quota") from e
                raise

            # backoff (attempt starts at 1 for helper)
            _sleep_with_backoff(attempt=attempt + 1, base=base_backoff, cap=cap_backoff)

    raise last_err if last_err else RuntimeError("Unknown error in ai_generate_deepen")