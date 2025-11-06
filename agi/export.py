# agi/export.py
from __future__ import annotations
from typing import List

def build_reflection_markdown(*, created_at=None, theme="", reflection="", insight="", mantra="", tags=None, mood=None, stillness_note=None):
    tags_line = ", ".join(tags or []) if tags else ""
    md = [
        f"# Reflection — {theme}",
        f"- **When:** {created_at or ''}",
        f"- **Mood:** {mood or '—'}",
        f"- **Tags:** {tags_line or '—'}",
        f"- **Stillness note:** {stillness_note or '—'}",
        "",
        "## Your Reflection",
        (reflection or "").strip() or "—",
    ]
    if insight or mantra:
        md += ["", "## Mentor Insight", insight or "—", "", f"*{(mantra or '').strip()}*"]
    return "\n".join(md)