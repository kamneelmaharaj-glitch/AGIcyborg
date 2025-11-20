# agi/journal_ai.py
from __future__ import annotations
import re
from typing import Optional, Dict, List

# --- light lexicons (tunable) ---
_POS = {
    "calm","grateful","peace","peaceful","ease","clear","focused","open",
    "soft","present","balanced","joy","steady","grounded","aligned","hope",
    "trust","love","compassion","kind","brave","curious","tender","forgive"
}
_NEG = {
    "tired","overwhelmed","anxious","anxiety","worry","worried","fear",
    "angry","frustrated","sad","tense","pressure","stressed","stress",
    "confused","uncertain","lost","guilty","shame","regret","restless",
}

_PILLAR_KEYWORDS = {
    "Awareness":  {"notice","noticed","observe","observed","aware","attention","breath","stillness","present","presence","clarity","insight","mindful"},
    "Balance":    {"balance","balanced","boundaries","rest","sleep","nutrition","movement","exercise","walk","pace","routine","time","schedule"},
    "Service":    {"help","serve","support","offer","give","contribute","family","team","humanity","kindness","mentor","guide"},
    "Reflection": {"reflect","reflection","journal","lesson","learned","learning","review","integrate","refine","iterate","improve"},
}

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")

def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())

def _sentiment_score(text: str) -> float:
    """Very small heuristic polarity score in [-1, 1]."""
    toks = _tokenize(text)
    if not toks:
        return 0.0
    pos = sum(1 for t in toks if t in _POS)
    neg = sum(1 for t in toks if t in _NEG)
    total = pos + neg
    if total == 0:
        return 0.0
    raw = (pos - neg) / total  # -1..+1
    # gently compress extremes if text is very short
    if len(toks) < 30:
        raw *= 0.8
    return max(-1.0, min(1.0, raw))

def _tone_label(score: float) -> str:
    if score >= 0.25:  return "positive"
    if score <= -0.25: return "tense"
    return "neutral"

def _summarize(text: str, max_chars: int = 220) -> str:
    # extract up to 2 concise sentences
    sents = [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]
    if not sents:
        return ""
    summary = sents[0]
    if len(summary) < max_chars and len(sents) > 1:
        cand = f"{summary} {sents[1]}"
        summary = cand if len(cand) <= max_chars else summary
    # final trim with ellipsis if still long
    return (summary[: max_chars - 1] + "…") if len(summary) > max_chars else summary

def _pillar(text: str) -> str:
    toks = set(_tokenize(text))
    best, best_count = "Awareness", 0
    for pillar, kws in _PILLAR_KEYWORDS.items():
        c = len(toks.intersection(kws))
        if c > best_count:
            best, best_count = pillar, c
    return best

def _guidance(tone: str, sentiment: float, energy: Optional[float], presence: Optional[float]) -> str:
    # simple, compassionate one-liner
    delta = None
    if energy is not None and presence is not None:
        delta = (energy or 0.0) - (presence or 0.0)

    if tone == "tense":
        if delta is not None and delta > 0.2:
            return "Let energy settle into the body: slow your exhale and feel the feet before deciding."
        return "Keep it simple today: one small honest action, then a mindful pause."

    if tone == "positive":
        if delta is not None and delta < -0.2:
            return "Your presence is strong—channel it into one clear step that matters."
        return "Honor the good signal: write one sentence intention and take the next right step."

    # neutral
    if delta is not None and abs(delta) > 0.3:
        return "Invite coherence: three soft breaths, lengthen the exhale, then choose the smallest helpful action."
    return "Return to the center with one minute of quiet attention, then move with ease."

def build_journal_insight(
    text: str,
    energy_score: Optional[float] = None,
    presence_score: Optional[float] = None,
) -> Dict[str, object]:
    text = (text or "").strip()
    sentiment = _sentiment_score(text)
    tone = _tone_label(sentiment)
    summary = _summarize(text)
    pillar = _pillar(text)
    guidance = _guidance(tone, sentiment, energy_score, presence_score)

    # lightweight tag suggestions (very gentle)
    toks = set(_tokenize(text))
    suggested_tags = list((toks & (_POS | _NEG | {"family","work","service","focus","rest","sleep","walk","code","music","guitar","finance","health"})) or [])

    return {
        "summary": summary,
        "tone": tone,
        "sentiment": round(float(sentiment), 3),
        "pillar": pillar,
        "guidance": guidance,
        "suggested_tags": suggested_tags[:5],
        "coherence_delta": None if (energy_score is None or presence_score is None)
                            else round(float((energy_score or 0) - (presence_score or 0)), 3),
    }

# --- simple pretty renderer for Streamlit (optional) ---
def render_journal_insight(card: dict) -> None:
    import streamlit as st  # local import to avoid hard dep if used elsewhere
    if not card:
        return
    tone_badge = {"positive":"✅", "neutral":"🟢", "tense":"🟠"}.get(card.get("tone"), "🟢")
    with st.container(border=True):
        st.markdown("#### 🧭 Reflective Mind")
        st.caption(f"{tone_badge} Tone: **{card.get('tone','—')}** • Sentiment: **{card.get('sentiment','—')}** • Pillar: **{card.get('pillar','—')}**")
        if card.get("summary"):
            st.write(f"**Today’s essence:** {card['summary']}")
        if card.get("guidance"):
            st.info(card["guidance"])
        tags = card.get("suggested_tags") or []
        if tags:
            st.caption("Suggested tags: " + ", ".join(f"`{t}`" for t in tags))
        if card.get("coherence_delta") is not None:
            st.caption(f"Energy–Presence delta: {card['coherence_delta']:+.2f}")