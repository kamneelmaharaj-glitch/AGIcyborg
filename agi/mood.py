# agi/mood.py
from __future__ import annotations

import re
from typing import Dict, List, Tuple


_MOODS: Tuple[str, ...] = (
    "soft",
    "heavy",
    "drained",
    "clear",
    "tender",
    "focused",
    "overwhelmed",
)

# Tie-break priority when scores tie (left wins)
_TIEBREAK: Tuple[str, ...] = (
    "overwhelmed",
    "drained",
    "heavy",
    "tender",
    "focused",
    "soft",
    "clear",
)

# Keyword/phrase signals (keep these small + high-signal for v1)
_KEYWORDS: Dict[str, List[str]] = {
    "soft": [
        "gentle", "soft", "ease", "okay", "allow", "steady", "calm",
    ],
    "clear": [
        "clear", "truth", "true", "simple", "know", "decide", "honest",
    ],
    "focused": [
        "will", "next", "today", "step", "plan", "focus", "do",
    ],
    "tender": [
        "care", "kind", "heart", "hold", "warm", "safe", "gentleness",
    ],
    "heavy": [
        "hard", "weight", "burden", "struggle", "painful", "stuck",
    ],
    "drained": [
        "tired", "exhausted", "numb", "empty", "worn", "drained",
    ],
    "overwhelmed": [
        "too much", "overwhelmed", "can't", "cannot", "everything", "pressure",
    ],
}

# Canonical samples (deterministic anchor texts)
_SAMPLES: Dict[str, str] = {
    "soft": "I can slow down. It is okay to ease into today.",
    "clear": "I know what needs to be said. I will say it simply.",
    "focused": "Next I will write the one sentence. Then I will send it.",
    "tender": "I want to be kind to my heart right now. I will be gentle.",
    "heavy": "This feels hard. I am carrying a lot and it weighs on me.",
    "drained": "I feel tired. Empty. I don't have much left.",
    "overwhelmed": "It's too much. Everything is piling up. I can't keep up.",
}

_WORD_RE = re.compile(r"[a-zA-Z']+")

_STOPWORDS = {
    "the","a","an","and","or","but","if","then","so","to","of","in","on","for","with","as","at","by",
    "i","me","my","mine","you","your","yours","we","our","ours","it","this","that","these","those",
    "is","am","are","was","were","be","being","been","do","does","did","have","has","had","will","would",
    "can","could","should","may","might","must","not","no","yes","just","very","really","right","now"
}


def _normalize(text: str) -> str:
    t = (text or "").strip().lower()
    t = t.replace("’", "'")
    t = re.sub(r"\s+", " ", t)
    return t


def _count_sentences(text: str) -> int:
    parts = re.split(r"[.!?]+", text)
    return sum(1 for p in parts if p.strip())


def _tokenize(text: str) -> List[str]:
    return _WORD_RE.findall((text or "").lower().replace("’", "'"))


def _tokenize_filtered(text: str) -> List[str]:
    toks = [t.lower() for t in _tokenize(text)]
    toks = [t for t in toks if t not in _STOPWORDS and len(t) >= 2]
    return toks


def _score_keywords(norm: str, tokens: List[str], mood: str) -> int:
    score = 0
    token_set = set(tokens)

    for kw in _KEYWORDS.get(mood, []):
        if " " in kw:
            if kw in norm:
                score += 2  # phrases count more
        else:
            if kw in token_set:
                score += 1
    return score


def _bow(tokens: List[str]) -> Dict[str, int]:
    d: Dict[str, int] = {}
    for t in tokens:
        d[t] = d.get(t, 0) + 1
    return d


def _cosine(a: Dict[str, int], b: Dict[str, int]) -> float:
    if not a or not b:
        return 0.0
    dot = 0
    for k, av in a.items():
        bv = b.get(k)
        if bv:
            dot += av * bv
    na = sum(v * v for v in a.values()) ** 0.5
    nb = sum(v * v for v in b.values()) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _sample_similarity_score(norm: str) -> Dict[str, float]:
    """
    Returns a small deterministic similarity score per mood,
    based on cosine(text, sample).
    """
    vec = _bow(_tokenize_filtered(norm))
    out: Dict[str, float] = {m: 0.0 for m in _MOODS}
    for m, sample in _SAMPLES.items():
        out[m] = _cosine(vec, _bow(_tokenize_filtered(sample)))
    return out


def detect_mood(reflection_text: str) -> str:
    """
    Deterministic mood classifier for reflection language texture.
    Returns one of: soft, heavy, drained, clear, tender, focused, overwhelmed
    """
    norm = _normalize(reflection_text)

    # If there's basically no language signal, don't label it "clear".
    if not norm or not _WORD_RE.search(norm):
        return "soft"   # or "drained" — pick your philosophy
    
    tokens = _tokenize(norm)
    token_set = set(tokens)

    comma_count = norm.count(",")
    semicolon_count = norm.count(";")
    ellipsis_count = norm.count("...")

    sentence_count = _count_sentences(norm)
    word_count = max(1, len(tokens))
    avg_wps = word_count / max(1, sentence_count)

    # Base integer scores
    scores: Dict[str, float] = {m: 0.0 for m in _MOODS}

    # --- keyword scoring ---
    for m in _MOODS:
        scores[m] += float(_score_keywords(norm, tokens, m))

    # --- structure scoring ---
    if comma_count >= 3:
        scores["overwhelmed"] += 2.0
    if semicolon_count >= 1:
        scores["overwhelmed"] += 1.0
    if ellipsis_count >= 1:
        scores["overwhelmed"] += 1.0
    if avg_wps >= 18:
        scores["overwhelmed"] += 1.0

    if word_count <= 20:
        scores["drained"] += 1.0
    if sentence_count >= 1 and avg_wps <= 7:
        scores["drained"] += 1.0

    if avg_wps >= 14:
        scores["heavy"] += 1.0

    if comma_count == 0 and semicolon_count == 0 and ellipsis_count == 0:
        scores["clear"] += 1.0
    if sentence_count <= 2 and word_count <= 45:
        scores["clear"] += 1.0

    if " i will " in f" {norm} " or " i'll " in f" {norm} ":
        scores["focused"] += 1.0

    if "heart" in token_set and comma_count <= 2:
        scores["tender"] += 1.0

    if any(w in token_set for w in ("calm", "steady", "ease")) and comma_count <= 2:
        scores["soft"] += 1.0

    # --- sample similarity (small weight, stabilizer) ---
    sim = _sample_similarity_score(norm)
    # Weight: 0.0–1.0 cosine -> add up to +1.2 points
    for m in _MOODS:
        scores[m] += 1.2 * sim.get(m, 0.0)

    # pick best with tiebreak
    best_score = max(scores.values())
    contenders = [m for m, sc in scores.items() if sc == best_score]

    if len(contenders) == 1:
        return contenders[0]

    for m in _TIEBREAK:
        if m in contenders:
            return m

    return "soft"