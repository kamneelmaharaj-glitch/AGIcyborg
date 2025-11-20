# agi/deepen_store.py
from __future__ import annotations
from typing import Optional

def save_deepen_ai(sb,
                   user_id: str,
                   theme: str,
                   followup_note: str,
                   insight: str,
                   microstep: str) -> None:
    """
    Writes to a small table `user_followup_ai` (create if not present).
    Columns: created_at (default), user_id, theme, followup_note, insight, microstep
    """
    try:
        sb.table("user_followup_ai").insert({
            "user_id": user_id,
            "theme": theme,
            "followup_note": followup_note,
            "insight": insight,
            "microstep": microstep,
        }).execute()
    except Exception:
        # Non-blocking: if table doesn't exist yet, UX should continue.
        pass