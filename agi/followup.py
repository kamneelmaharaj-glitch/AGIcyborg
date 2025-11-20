# agi/followup.py — Deepen + micro-steps + analytics

from __future__ import annotations

import streamlit as st
from typing import List, Tuple, Optional
from collections import Counter
from datetime import datetime, timedelta, timezone

from agi.ai import ai_generate
from agi.auth import S_USER_ID
from agi.orb import render_breath_orb
from agi.presence import PRESENCE_TOGGLE_KEY, render_presence_widget
from agi.config import PRESENCE_CYCLE_SEC


# Orb Helper CSS

def _ensure_orb_css() -> None:
    """Load lightweight breathing-orb styles once."""
    if st.session_state.get("_orb_css_loaded"):
        return

    st.markdown(
        """
<style>
.orb-wrapper {
  padding: 1rem 0 0.5rem 0;
  text-align: center;
}

.orb-title-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: .4rem;
  margin-bottom: .3rem;
}

.orb-title-row span.label {
  font-weight: 600;
  font-size: 0.98rem;
}

.orb-subtitle {
  font-size: 0.85rem;
  opacity: 0.8;
  margin-bottom: 0.8rem;
}

.orb-circle {
  width: 220px;
  height: 220px;
  max-width: 60vw;
  border-radius: 50%;
  margin: 0 auto;
  background: radial-gradient(circle at 30% 20%,
      rgba(180,255,240,0.9),
      rgba(40,110,110,0.95),
      rgba(10,26,30,1));
  box-shadow:
    0 0 40px rgba(120,255,220,0.45),
    0 0 80px rgba(40,120,110,0.7);
  animation: orbBreath 6s ease-in-out infinite;
}

@keyframes orbBreath {
  0%   { transform: scale(0.96); box-shadow: 0 0 28px rgba(120,255,220,0.35); }
  35%  { transform: scale(1.02); box-shadow: 0 0 40px rgba(120,255,220,0.55); }
  70%  { transform: scale(0.97); box-shadow: 0 0 30px rgba(120,255,220,0.40); }
  100% { transform: scale(0.96); box-shadow: 0 0 28px rgba(120,255,220,0.35); }
}

.orb-instruction {
  font-size: 0.9rem;
  margin-top: 0.9rem;
  opacity: 0.85;
}
</style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state["_orb_css_loaded"] = True


def render_breath_orb() -> None:
    """Simplified breathing orb with gentle instructions."""
    _ensure_orb_css()

    st.markdown(
        """
<div class="orb-wrapper">
  <div class="orb-title-row">
    <span>🪷</span>
    <span class="label">Return to stillness</span>
  </div>
  <div class="orb-subtitle">
    Breathe 4–2–6 and gently notice three sensations.
  </div>
  <div class="orb-circle"></div>
  <div class="orb-instruction">
    Inhale… Exhale…<br/>
    Notice any touch, temperature, or weight.
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

from agi.auth import S_USER_ID  # you already import this near the top


PRESENCE_TOGGLE_KEY = "presence_toggle_global"

def render_today_panel(sb, user_id) -> None:
    """
    Today panel: single source of truth for Presence toggle + orb,
    and then the micro-step card underneath.
    """
    box = st.container(border=True)

    with box:
        # --- Header row ---
        header_left, header_right = st.columns([3, 1])
        with header_left:
            st.markdown("### 🌅 Today")
            st.caption("Return to stillness — 4–2–6 and notice three sensations.")
        with header_right:
            # This is the *only* widget that writes to PRESENCE_TOGGLE_KEY.
            presence_on = st.toggle(
                "Presence",
                key=PRESENCE_TOGGLE_KEY,
                value=st.session_state.get(PRESENCE_TOGGLE_KEY, False),
                help="When on, the orb pulses with the 4–2–6 rhythm.",
            )

        # --- Orb block ---
        if presence_on:
            # Animated orb (uses the same CSS class + timing as Presence Mode)
            st.markdown(
                f"""
                <div style="display:flex;justify-content:center;margin-top:.75rem;">
                  <div class="presence-orb"
                       style="animation-duration:{PRESENCE_CYCLE_SEC}s"></div>
                </div>
                <div class="presence-phase"
                     style="text-align:center;margin-top:.4rem;">
                  Inhale… Exhale…
                </div>
                <div style="text-align:center;opacity:.7;font-size:.9rem;margin-top:.25rem;">
                  Notice any touch, temperature, or weight.
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            # Static / gentle orb using the legacy widget
            render_presence_widget(
                phase="Inhale… Exhale…",
                hint="Notice any touch, temperature, or weight.",
            )

    # --- Below the Today card: Today’s micro-step ---
    render_microstep_widget(sb, user_id)

def _why_it_matters_line(theme: str, microstep: str) -> str:
    """Generate a short supportive line for today's microstep."""
    base = "This small action has weight today because"

    lines = {
        "Clarity":     f"{base} it sharpens your inner seeing.",
        "Presence":    f"{base} it brings you back to breath and truth.",
        "Courage":     f"{base} it strengthens your ability to move forward.",
        "Compassion":  f"{base} it opens your heart to what is real.",
        "Surrender":   f"{base} it helps you release what you cannot hold.",
        "Calm-Sage":   f"{base} it deepens your grounded wisdom.",
    }

    # If theme unknown: generic fallback
    return lines.get(theme, f"{base} it aligns you with your Dharma.")

# ---------------------------------------------------------------------------
# CSS (once)
# ---------------------------------------------------------------------------

def _ensure_fu_css() -> None:
    if st.session_state.get("_fu_css_loaded"):
        return
    st.markdown(
        """
<style>
.fu-ribbon {
  margin-top: .5rem;
  padding: .6rem .8rem;
  border-radius: 10px;
  background:
    radial-gradient(120% 120% at 0% 0%, rgba(64,255,160,.20), rgba(40,44,52,.35) 70%),
    rgba(22,26,31,.35);
  border: 1px solid rgba(64,255,160,.30);
  box-shadow: 0 0 0 0 rgba(64,255,160,.30);
  animation: fuGlow 1.4s ease-out 1;
  font-size: .92rem;
}
@keyframes fuGlow {
  0%   { box-shadow: 0 0 0 0 rgba(64,255,160,.35); }
  100% { box-shadow: 0 0 0 22px rgba(64,255,160,0); }
}
.fu-history-item {
  padding:.6rem .75rem;
  border:1px solid rgba(255,255,255,.08);
  border-radius:.75rem;
}
</style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state["_fu_css_loaded"] = True


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_sb():
    """Return Supabase client from session or lazily create it."""
    sb = st.session_state.get("sb")
    if sb is not None:
        return sb
    try:
        from agi.db import get_client

        sb = get_client()
        st.session_state["sb"] = sb
        return sb
    except Exception as e:  # pragma: no cover - purely defensive
        st.warning(f"DB not available: {e}")
        return None


def _iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _fmt_when(ts: Optional[str]) -> str:
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%b %d, %Y • %H:%M UTC")
    except Exception:
        return ts or "—"


# ---------------------------------------------------------------------------
# AI helpers (Deepen)
# ---------------------------------------------------------------------------

_SYSTEM_PRIMER = (
    "You are a compassionate mentor. Speak simply and briefly. "
    "Offer one gentle insight and one tiny 2-minute action."
)


def _compose_prompt(
    theme: str,
    reflection_text: str,
    followup_note: str,
    recent_followups: Optional[List[str]],
) -> str:
    history = " • ".join((recent_followups or [])[-5:]) or "—"
    return (
        f"[SYSTEM]\n{_SYSTEM_PRIMER}\n\n"
        f"[CONTEXT]\nTheme: {theme}\n"
        f"Reflection: {reflection_text.strip()}\n"
        f"Follow-up note: {followup_note.strip()}\n"
        f"Recent follow-ups: {history}\n\n"
        "[TASK]\n"
        "Return exactly two lines:\n"
        "INSIGHT: <one sentence>\n"
        "MICROSTEP: <one tiny step I can do in < 2 minutes>"
    )


def _generate_deepen_insight(
    theme: str,
    reflection_text: str,
    followup_note: str,
    recent_followups: Optional[List[str]],
) -> Tuple[str, str]:
    """
    Use ai_generate(theme, text) -> (insight, microstep_like).

    We are tolerant of prefixes like 'INSIGHT:' / 'MICROSTEP:' and we
    guarantee that the returned microstep is non-empty by falling back
    to the note / insight if needed.
    """
    prompt = _compose_prompt(theme, reflection_text, followup_note, recent_followups)
    raw_insight, raw_second = ai_generate(theme, prompt)

    def strip_prefix(s: str) -> str:
        s = (s or "").strip()
        for pfx in ("INSIGHT:", "Insight:", "MICROSTEP:", "Microstep:"):
            if s.startswith(pfx):
                return s[len(pfx):].strip()
        return s

    insight = strip_prefix(raw_insight)
    microstep = strip_prefix(raw_second)

    # Fallback: if model did not give us a useful second line, synthesize one
    if not microstep:
        base = (followup_note or "").strip() or insight or "this reflection"
        microstep = (
            "Take one tiny 2-minute action today to honour this: "
            f"{base}"
        )

    return insight, microstep


# ---------------------------------------------------------------------------
# Analytics helpers (user_followup_ai)
# ---------------------------------------------------------------------------

def _dates_streak(dts: List[datetime]) -> int:
    """Count how many consecutive days (including today) have at least one entry."""
    if not dts:
        return 0
    today = _utc_now().date()
    days_with = {dt.date() for dt in dts}
    streak, cursor = 0, today
    while cursor in days_with:
        streak += 1
        cursor = cursor - timedelta(days=1)
    return streak


def _fetch_followups_window(
    sb,
    user_id: str,
    days: int = 30,
    theme: Optional[str] = None,
):
    """
    Return (rows, error_string) for user_followup_ai in a time window.
    Rows contain created_at + theme.
    """
    try:
        since = (_utc_now() - timedelta(days=days)).isoformat()
        q = (
            sb.table("user_followup_ai")
              .select("created_at, theme")
              .eq("user_id", user_id)
              .gte("created_at", since)
              .order("created_at", desc=True)
        )
        if theme:
            q = q.eq("theme", theme)
        res = q.execute()
        return (res.data or [], None)
    except Exception as e:  # pragma: no cover
        return ([], str(e))


def render_followup_analytics(
    sb,
    user_id: str,
    *,
    days_short: int = 7,
    days_long: int = 30,
    theme: Optional[str] = None,
) -> None:
    """
    Compact metrics row: This week • Last 30d • Streak • Top theme.
    Based on user_followup_ai, not micro-step completion.
    """
    rows_long, err = _fetch_followups_window(sb, user_id, days=days_long, theme=theme)
    if err:
        st.caption(f"Follow-up analytics unavailable: {err}")
        return

    # Parse timestamps + themes
    dts_long: List[datetime] = []
    themes_long: List[str] = []
    for r in rows_long:
        try:
            dt = datetime.fromisoformat((r.get("created_at") or "").replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dts_long.append(dt)
            themes_long.append((r.get("theme") or "").strip() or "—")
        except Exception:
            continue

    # Short window count (7 days)
    rows_short, _ = _fetch_followups_window(sb, user_id, days=days_short, theme=theme)
    total_short = len(rows_short)
    total_long = len(rows_long)

    # Streak (daily)
    streak = _dates_streak(dts_long)

    # Top theme
    top_theme = "—"
    if themes_long:
        c = Counter(themes_long)
        top_theme, _ = c.most_common(1)[0]

    # Last follow-up timestamp
    last_when = "—"
    if dts_long:
        last_when = (
            max(dts_long)
            .astimezone(timezone.utc)
            .strftime("%b %d, %Y • %H:%M UTC")
        )

    # --- UI ---
    scope_label = theme or "All themes"
    st.markdown(f"#### 📈 Follow-up insights — {scope_label}")
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    c1.metric("This week", total_short)
    c2.metric("Last 30 days", total_long)
    c3.metric("Streak (days)", streak)
    c4.metric("Top theme", top_theme if top_theme != "" else "—")
    st.caption(f"Scope: {scope_label} • Last follow-up: {last_when}")
    st.markdown("---")

# ---------- Micro-step helpers (single-source-of-truth) ----------

def _set_microstep_done(sb, row_id: str, done: bool) -> None:
    """
    Mark a micro-step as done/undone by setting microstep_done_at.
    Best-effort: errors are swallowed so the UI never crashes.
    """
    if not sb or not row_id:
        return

    try:
        payload = {
            "microstep_done_at": _iso_utc() if done else None,
        }
        (
            sb.table("user_followup_ai")
              .update(payload)
              .eq("id", row_id)
              .execute()
        )
    except Exception:
        # If the column doesn't exist, we just don't persist the done state.
        pass

def _microstep_streak(
    sb,
    user_id: str,
    days: int = 30,
) -> Tuple[int, int, int]:
    """
    Return (streak, completed_last_7, completed_last_30) for micro-steps.

    We only count rows where microstep_done_at is not null.
    """
    if not (sb and user_id):
        return 0, 0, 0

    try:
        since = (_utc_now() - timedelta(days=days)).isoformat()
        res = (
            sb.table("user_followup_ai")
              .select("microstep_done_at")
              .eq("user_id", user_id)
              .not_.is_("microstep_done_at", "null")
              .gte("microstep_done_at", since)
              .order("microstep_done_at", desc=True)
              .execute()
        )
        rows = res.data or []
    except Exception:
        return 0, 0, 0

    dts: List[datetime] = []
    for r in rows:
        ts = r.get("microstep_done_at")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dts.append(dt)
        except Exception:
            continue

    if not dts:
        return 0, 0, 0

    # Streak based on completion dates
    streak = _dates_streak(dts)

    today = _utc_now().date()
    completed_7 = sum(
        1 for dt in dts if (today - dt.date()).days < 7
    )
    completed_30 = len(dts)

    return streak, completed_7, completed_30

def _list_microsteps(sb, user_id: str, days: int = 7) -> List[dict]:
    """
    Return recent micro-steps for this user from user_followup_ai, newest first.

    For each row we compute:
      - micro_text: microstep / followup_note / insight fallback
      - done: bool from microstep_done_at (if present)
    """
    if not (sb and user_id):
        return []

    since = (_utc_now() - timedelta(days=days)).isoformat()

    try:
        res = (
            sb.table("user_followup_ai")
              .select(
                  "id, created_at, theme, followup_note, insight, microstep, microstep_done_at"
              )
              .eq("user_id", user_id)
              .gte("created_at", since)
              .order("created_at", desc=True)
              .limit(50)
              .execute()
        )
    except Exception:
        # If the select fails for any reason, just show no micro-steps.
        return []

    rows = res.data or []
    processed: List[dict] = []

    for r in rows:
        text = (r.get("microstep") or "").strip() \
            or (r.get("followup_note") or "").strip() \
            or (r.get("insight") or "").strip()

        if not text:
            # Absolutely nothing to show, skip this row
            continue

        r["micro_text"] = text
        r["done"] = bool(r.get("microstep_done_at"))
        processed.append(r)

    return processed


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def render_microstep_widget(sb, user_id: str) -> None:
    """
    Show 'Today’s micro-step' under the orb.

    - Main card: latest micro-step *from today* (UTC)
    - History: all micro-steps from the last 7 days
    """
    # Ensure we have a DB client + user id
    if sb is None:
        sb = _get_sb()
    if not user_id:
        user_id = st.session_state.get(S_USER_ID)

    # --- Load all recent micro-steps ---
    rows = _list_microsteps(sb, user_id=user_id, days=7)

    # 🔹 Compute micro-step streak numbers
    streak, completed_7, completed_30 = _microstep_streak(sb, user_id)

    # Filter to "today only" for the main card
    today = _utc_now().date()
    today_rows: List[dict] = []
    for r in rows:
        dt = _parse_ts(r.get("created_at"))
        if dt and dt.date() == today:
            today_rows.append(r)

    latest = today_rows[0] if today_rows else None

    # --- Main card container ---
    box = st.container(border=True)
    with box:
        followup_id = (latest or {}).get("id")
        done_key = f"microstep_done::{followup_id}" if followup_id else "microstep_done::none"

        is_done_db = bool((latest or {}).get("done"))
        is_done_state = bool(st.session_state.get(done_key, False))
        is_done = is_done_db or is_done_state

        title = "🧭 Today’s micro-step"
        if is_done and followup_id:
            title += " ✅"

        st.subheader(title)

        if not latest:
            st.caption(
                "No micro-steps for today yet. After you use **Deepen** on a reflection, "
                "your tiny action for today will appear here."
            )
        else:
            theme = (latest.get("theme") or "Reflection").strip() or "Reflection"
            created_at = _fmt_when(latest.get("created_at"))
            micro_text = latest.get("micro_text", "—")

            st.caption(f"{theme} • Last follow-up: {created_at}")
            st.write(f"**Tiny action:** {micro_text}")

            # 🌱 Step 2: “Why this matters” line
            why_line = _why_it_matters_line(theme, micro_text)
            st.markdown(
                f"<div style='color:rgba(255,255,255,.75); "
                f"font-size:.9rem; margin-top:.4rem;'>"
                f"🪷 <em>{why_line}</em>"
                f"</div>",
                unsafe_allow_html=True,
            )

            # 🔹 Streak line
            if streak > 0:
                st.caption(
                    f"Streak: {streak} day{'s' if streak != 1 else ''} in a row • "
                    f"Done last 7 days: {completed_7}"
                )
            else:
                st.caption(
                    "Streak: Begin your first day by completing this tiny action ✨"
                )

            # ✅ Done toggle (always available when there is a microstep today)
            new_done = st.checkbox(
                "Mark this micro-step as done for today",
                value=is_done,
                key=done_key,
            )

            if new_done != is_done and followup_id and sb and user_id:
                _set_microstep_done(sb, followup_id, new_done)
                st.session_state[done_key] = new_done
                st.rerun()

    # --- Micro-step history (last 7 days) ---
    if not rows:
        return

    with st.expander("🧾 Micro-step history (last 7 days)", expanded=False):
        for r in rows:
            rid   = r.get("id")
            when  = _fmt_when(r.get("created_at"))
            theme = (r.get("theme") or "—").strip() or "—"
            text  = r.get("micro_text", "—")
            done  = bool(r.get("done"))

            row_box = st.container()
            with row_box:
                st.markdown(f"**{when} • {theme}**")
                st.write(f"**Tiny action:** {text}")

                c1, c2 = st.columns([2, 1])
                with c1:
                    st.write("**Status:** " + ("✅ marked done" if done else "⏳ not marked done"))

                if rid and sb and user_id:
                    with c2:
                        if done:
                            if st.button(
                                "Undo",
                                key=f"ms_undo::{rid}",
                                help="Mark this micro-step as not done",
                            ):
                                _set_microstep_done(sb, rid, False)
                                st.rerun()
                        else:
                            if st.button(
                                "Mark done",
                                key=f"ms_done::{rid}",
                                help="Mark this micro-step as done for that day",
                            ):
                                _set_microstep_done(sb, rid, True)
                                st.rerun()
# ---------------------------------------------------------------------------
# Persistence (user_reflections + user_followup_ai)
# ---------------------------------------------------------------------------

def _save_followup_note_to_latest(sb, user_id: str, note: str) -> Optional[str]:
    """
    Save follow-up note to the latest reflection for the user and
    return that reflection id.
    """
    res = (
        sb.table("user_reflections")
          .select("id, created_at")
          .eq("user_id", user_id)
          .order("created_at", desc=True)
          .limit(1)
          .execute()
    )
    rid = (res.data or [{}])[0].get("id")
    if not rid:
        return None
    (
        sb.table("user_reflections")
          .update(
              {
                  "followup_note": note,
                  "followup_created_at": _iso_utc(),
              }
          )
          .eq("id", rid)
          .execute()
    )
    return rid


def _fetch_recent_followups(sb, user_id: str) -> List[str]:
    """Recent follow-up notes (for AI context)."""
    try:
        res = (
            sb.table("user_reflections")
              .select("followup_note")
              .eq("user_id", user_id)
              .not_.is_("followup_note", "null")
              .order("created_at", desc=True)
              .limit(5)
              .execute()
        )
        return [
            r["followup_note"]
            for r in (res.data or [])
            if r.get("followup_note")
        ]
    except Exception:
        return []


def _save_followup_ai(
    sb,
    *,
    user_id: str,
    reflection_id: Optional[str],
    theme: str,
    note: str,
    insight: str,
    microstep: str,
) -> bool:
    """
    Append a record to user_followup_ai (best-effort).
    Returns True on success, False on failure so callers can skip st.rerun().
    """
    if not sb or not user_id:
        st.error("DB client or user_id missing when saving follow-up.")
        return False

    payload = {
        "user_id": user_id,
        "reflection_id": reflection_id,
        "theme": theme,
        "followup_note": note,
        "insight": insight,
        "microstep": microstep,
        "meta": {"source": "deepen", "model": "mentor-ai"},
        "created_at": _iso_utc(),  # ensure non-null created_at
    }

    try:
        res = sb.table("user_followup_ai").insert(payload).execute()
        # Optional debug, you can remove after things work:
        inserted_id = (res.data or [{}])[0].get("id")
        st.caption(f"DEBUG: follow-up saved (id={inserted_id})")
        return True
    except Exception as e:
        # ⬅️ This is the message we really need to see
        st.error(f"Couldn’t save follow-up (DB error): {e}")
        return False

# ---------------------------------------------------------------------------
# UI building blocks
# ---------------------------------------------------------------------------

def _render_ai_card(theme: str, insight: str, microstep: str) -> None:
    card = st.container(border=True)
    with card:
        st.caption(f"Deepen Mentor — {theme or 'Reflection'}")
        st.write(f"**Insight:** {insight or '—'}")
        st.write(f"**Micro-step:** {microstep or '—'}")

# ---------------------------------------------------------------------------
# Public API — Deepen main panel
# ---------------------------------------------------------------------------

def render_mentor_followup(
    theme: str,
    reflection_text: str,
    row_id: Optional[str] = None,
) -> None:
    """
    Main entry point used by app.py.

    Layout:
      • Top: Deepen note editor + Save button + one-time ribbon
      • Right column: latest AI (Insight + Micro-step)
      • Below: analytics strip
    """
    _ensure_fu_css()
    sb = _get_sb()
    user_id = st.session_state.get(S_USER_ID)

    # Scope keys per reflection (or theme fallback) to avoid collisions
    scope = row_id or f"theme::{theme or 'default'}"
    res_key = f"deepen_ai::{scope}"
    rib_key = f"fu_ribbon::{scope}"
    note_key = f"followup_quick_note::{scope}"

    if res_key not in st.session_state:
        st.session_state[res_key] = {"insight": "", "microstep": ""}

    box = st.container(border=True)
    with box:
        st.caption("Mentor follow-up")
        st.subheader(f"Deepen — {theme or 'Reflection'}")
        st.write(
            "Gently explore one next thread from your reflection. "
            "Jot a single sentence intention."
        )

        # Context tail line (last line of reflection)
        last_line = (reflection_text or "").strip().splitlines()[-1:] or [""]
        if last_line and last_line[0]:
            st.caption(f"Last note: “{last_line[0]}”")

        left, right = st.columns([3, 1], gap="large")

        # ----- Left column: editor + save + ribbon -----
        with left:
            note = st.text_area(
                "Quick deepen note (optional, saved)",
                key=note_key,
                height=110,
                placeholder="E.g., 'One small step I’ll take in the next hour is…'",
            )

            if st.button("💾 Save follow-up", key=f"save_followup::{scope}"):
                if not sb or not user_id:
                    st.warning("Not signed in or DB unavailable.")
                else:
                    # 1) Save to latest reflection + generate AI result
                    try:
                        reflection_id = row_id or _save_followup_note_to_latest(
                            sb,
                            user_id,
                            note or "",
                        )

                        recent = _fetch_recent_followups(sb, user_id)
                        insight, microstep = _generate_deepen_insight(
                            theme=theme or "",
                            reflection_text=reflection_text or "",
                            followup_note=note or "",
                            recent_followups=recent,
                        )
                        st.session_state[res_key] = {
                            "insight": insight,
                            "microstep": microstep,
                        }

                    except Exception as e:
                        st.error(f"Couldn’t generate follow-up: {e}")
                    else:
                        # 2) Save to user_followup_ai (this is where Supabase might fail)
                        ok = _save_followup_ai(
                            sb,
                            user_id=user_id,
                            reflection_id=reflection_id,
                            theme=theme or "",
                            note=note or "",
                            insight=insight,
                            microstep=microstep,
                        )

                        if ok:
                            # 3) Only rerun if DB insert succeeded
                            st.session_state[rib_key] = True
                            st.rerun()
                        # If not ok, _save_followup_ai already showed st.error and we do NOT rerun

            # — Ribbon (shows once, then clears) —
            if st.session_state.get(rib_key):
                st.markdown(
                    '<div class="fu-ribbon">✅ Follow-up saved and deepened.</div>',
                    unsafe_allow_html=True,
                )
                st.session_state.pop(rib_key, None)

        # ----- Right column: current AI card -----
        with right:
            stored = st.session_state.get(res_key, {})
            _render_ai_card(
                theme,
                stored.get("insight", ""),
                stored.get("microstep", ""),
            )

        # ----- Analytics strip (theme-aware) -----
        if sb and user_id:
            render_followup_analytics(sb, user_id, theme=theme or None)