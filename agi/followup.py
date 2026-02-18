# agi/followup.py — Deepen + micro-steps + analytics

from __future__ import annotations

import streamlit as st
from typing import List, Tuple, Optional
from collections import Counter
from datetime import datetime, timedelta, timezone

from agi.deepen_ai import generate_deepen_insight
from agi.auth import S_USER_ID
from agi.orb import render_breath_orb
from agi.presence import PRESENCE_TOGGLE_KEY, render_presence_widget
from agi.config import PRESENCE_CYCLE_SEC
from agi.deepen_ai import get_last_deepen_debug as _get_last_deepen_debug
from agi.presence import presence_sensory_copy

# ----------------------------
# Theme resolution (follow-up)
# ----------------------------
def resolve_followup_theme() -> str:
    return (
        st.session_state.get("current_theme")
        or st.session_state.get("last_theme")
        or "Clarity"
    )

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

# ------------------------------------------------------------------
# Presence carry-over must be resolved BEFORE any UI reads tone/copy.
# ------------------------------------------------------------------
from agi.presence import infer_presence_carryover

def _ensure_presence_carry(state_row):
    if st.session_state.get("presence_carry"):
        return  # optional: don’t recompute every rerun

    try:
        carry = infer_presence_carryover(state_row)
        st.session_state["presence_carry"] = {
            "freshness": carry.freshness,
            "tone": carry.tone,
            "stage_carry": carry.stage_carry,
            "reason": carry.reason,
        }
    except Exception:
        st.session_state["presence_carry"] = {
            "freshness": "dormant",
            "tone": "normal",
            "stage_carry": None,
            "reason": "carry_error",
        }

    # ✅ NORMALIZE HERE (outside try/except)
    carry = st.session_state.get("presence_carry") or {}

    st.session_state["presence_carry"] = {
        **carry,
        "freshness": (carry.get("freshness") or "dormant"),
        "tone": (carry.get("tone") or "gentle"),
        "stage_carry": carry.get("stage_carry"),
        "reason": (carry.get("reason") or "defaulted"),
    }

def render_today_panel(sb, user_id) -> None:
    """
    Today panel: single source of truth for Presence toggle + orb,
    and then the micro-step card underneath.
    """
    box = st.container(border=True)

    # ✅ Define state before calling _ensure_presence_carry
    state = None
    try:
        # Use YOUR real getter here (whatever returns the reflection_state row)
        st_row = fetch_reflection_state_row(sb, user_id)  # <-- replace this line
        state = getattr(st_row, "data", None) or None
    except Exception:
        state = None

    _ensure_presence_carry(state)

    from agi.presence import presence_stage_label

    carry = st.session_state.get("presence_carry", {}) or {}
    stage = carry.get("stage_carry")
    stage_txt = presence_stage_label(stage)

    # tiny, non-intrusive cue
    if stage_txt:
        st.caption(f"Presence: {stage_txt}")

    import os

    if os.getenv("AGI_DEBUG") == "1" and stage_txt:
        st.caption(f"Presence: {stage_txt}")

    with box:
        # --- Presence sensory copy (always defined) ---
        tone = (st.session_state.get("presence_carry", {}) or {}).get("tone", "normal")
        # tone = "normal"  # TEMP TEST (optional)

        headline, hint = presence_sensory_copy(tone=tone)

        # --- Header row ---
        header_left, header_right = st.columns([3, 1])
        with header_left:
            st.markdown("### 🌅 Today")
            st.caption(headline)

        with header_right:
            presence_on = st.toggle(
                "Presence",
                key=PRESENCE_TOGGLE_KEY,
                value=st.session_state.get(PRESENCE_TOGGLE_KEY, False),
                help="When on, the orb pulses with the 4–2–6 rhythm.",
            )

        # --- Orb block ---
        if presence_on:
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
                  {hint}
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            render_presence_widget(
                phase="Inhale… Exhale…",
                hint=hint,
            )
   
        # -------------------------
        # DEBUG (only when AGI_DEBUG=1)
        # -------------------------
        if os.getenv("AGI_DEBUG") == "1":
            pc = st.session_state.get("presence_carry") or {}
            st.caption(
                f"Presence carry-over: {pc.get('freshness','dormant')} · "
                f"tone={pc.get('tone','gentle')} · "
                f"reason={pc.get('reason','defaulted')}"
            )
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
/* ---------------- Follow-up ribbon ---------------- */
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

/* ---------------- Micro-step card ---------------- */
.micro-main {
  animation: microFadeIn .45s ease-out;
}

@keyframes microFadeIn {
  0%   { opacity:0; transform: translateY(4px); }
  100% { opacity:1; transform: translateY(0); }
}

.micro-header {
  display:flex;
  align-items:center;
  justify-content:space-between;
  margin-bottom:.4rem;
}

.micro-label {
  font-size:.86rem;
  text-transform:uppercase;
  letter-spacing:.16em;
  opacity:.78;
}

.micro-theme-pill {
  padding:.15rem .6rem;
  border-radius:999px;
  border:1px solid rgba(255,255,255,.20);
  font-size:.8rem;
  opacity:.85;
}

.micro-body {
  margin-top:.3rem;
  font-size:.92rem;
}

.micro-tiny-label {
  font-size:.8rem;
  text-transform:uppercase;
  letter-spacing:.14em;
  opacity:.72;
}

.micro-tiny-text {
  margin-top:.15rem;
  opacity:.96;
}

.micro-why {
  margin-top:.45rem;
  font-size:.9rem;
  color:rgba(255,255,255,.78);
}

.micro-streak-row {
  margin-top:.55rem;
  font-size:.8rem;
  opacity:.8;
}

.micro-streak-row .value {
  font-weight:600;
  opacity:.92;
}

.micro-streak-row .dot {
  margin:0 .35rem;
}

.silence-pill {
  margin-left: 8px;
  padding: 2px 8px;
  font-size: 0.72rem;
  border-radius: 999px;
  background: rgba(180, 220, 255, 0.12);
  border: 1px solid rgba(180, 220, 255, 0.25);
  color: rgba(220, 235, 255, 0.9);
}

.silence-subcaption {
  margin-top: 6px;
  font-size: 0.82rem;
  opacity: 0.75;
  letter-spacing: 0.02em;
}

/* History rows reuse existing styling but stay minimal */
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
    Mark a micro-step as done/undone.

    We update:
      - microstep_done_at  (timestamp or NULL)
      - completion_status  (boolean)
      - completion_at      (timestamp or NULL)

    Any DB error is surfaced in the UI so we can see RLS / permission issues.
    """
    if not (sb and row_id):
        return

    try:
        now_iso = _iso_utc()

        payload = {
            "microstep_done_at": now_iso if done else None,
            "completion_status": bool(done),
            "completion_at":     now_iso if done else None,
        }

        res = (
            sb.table("user_followup_ai")
              .update(payload)
              .eq("id", row_id)
              .execute()
        )

        # Optional tiny debug hook if you ever want to inspect
        st.session_state[f"_last_ms_update::{row_id}"] = getattr(res, "data", None)

    except Exception as e:
        # ⚠️ Do NOT swallow this – we need to see any RLS / SQL errors
        st.error(f"Micro-step update failed: {e}")
        
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


# Microstep Widget
def render_microstep_widget(sb, user_id: str) -> None:
    """
    Show 'Today’s micro-step' under the orb.

    - Main card: latest micro-step *from today* (UTC)
    - History: all micro-steps from the last 7 days
    """

    # --- Ensure we have DB + user id ---
    if sb is None:
        sb = _get_sb()
    if not user_id:
        user_id = st.session_state.get(S_USER_ID)
    if not (sb and user_id):
        return

    # --- E2 READ: show last continuity state (non-intrusive) ---
    try:
        if sb and user_id:
            st_row = (
                sb.table("reflection_state")
                    .select(
                        "last_reflection_at,last_theme,last_mood,last_microstep,"
                        "last_meaningful_action,last_action_at,reflection_count"
                    )
                    .eq("user_id", str(user_id))
                    .maybe_single()
                    .execute()
            )
            state = getattr(st_row, "data", None) or None

            if state:
                last_ms = (state.get("last_microstep") or "").strip()
                last_theme = (state.get("last_theme") or "").strip()
                last_mood = (state.get("last_mood") or "").strip()

                st.caption(
                    f"Continuity: {last_theme or '—'} • {last_mood or '—'}"
                    + (f" • last microstep: “{last_ms}”" if last_ms else "")
            )
    except Exception:
        pass
    
       

    # --- Load recent micro-steps (last 7 days) ---
    rows = _list_microsteps(sb, user_id=user_id, days=7)

    # Streak + completion analytics (based on microstep_done_at)
    streak, completed_7, completed_30 = _microstep_streak(sb, user_id)

    # Filter to "today only" for the main card
    today = _utc_now().date()
    today_rows: List[dict] = []
    for r in rows:
        dt = _parse_ts(r.get("created_at"))
        if dt and dt.date() == today:
            today_rows.append(r)

    # Rows from _list_microsteps are already newest-first;
    # taking [0] gives us the latest micro-step for today.
    latest = today_rows[0] if today_rows else None

    # --- Main card container ---
    box = st.container(border=True)
    with box:
        followup_id = (latest or {}).get("id")
        done_key = (
            f"microstep_done::{followup_id}"
            if followup_id
            else "microstep_done::none"
        )

        # True/False coming from the database (via _list_microsteps)
        is_done_db = bool((latest or {}).get("done"))

        if latest:
            theme = (latest.get("theme") or "Reflection").strip() or "Reflection"
            created_at = _fmt_when(latest.get("created_at"))
            is_silenced = bool(latest.get("silenced"))

            st.markdown("### Today’s micro-step")
            st.caption(f"{theme} • Last follow-up: {created_at}")

            if is_silenced:
                # Silence day: no “task”, no checkbox
                st.markdown("🪷 *Stillness is active. Nothing to complete today.*")
                st.caption("If you want, write one gentle line in **Deepen** — or rest.")
            else:
                micro_text = (latest.get("micro_text") or "—").strip()

                st.write(f"**Tiny action:** {micro_text}")

                why_line = _why_it_matters_line(theme, micro_text)
                st.markdown(f"🪷 *{why_line}*")

                # Streak line
                if streak > 0:
                    st.caption(
                        f"Streak: {streak} day{'s' if streak != 1 else ''} in a row • "
                        f"Done last 7 days: {completed_7}"
                    )
                else:
                    st.caption("Streak: Begin your first day by completing this tiny action ✨")

                # ✅ Done toggle (only when not silenced)
                new_done = st.checkbox(
                    "Mark this micro-step as done for today",
                    value=is_done_db,
                    key=done_key,
                )

                if followup_id and sb and user_id and (new_done != is_done_db):
                    _set_microstep_done(sb, followup_id, new_done)
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
                    st.write(
                        "**Status:** "
                        + ("✅ marked done" if done else "⏳ not marked done")
                    )

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
# Persistence helpers for Deepen (user_followup_ai)
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


def _fetch_recent_followups(sb, user_id: str) -> list[str]:
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
        sb.table("user_followup_ai").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Couldn’t save follow-up (DB error): {e}")
        return False


def _load_latest_followup_ai(
    sb,
    user_id: Optional[str],
    reflection_id: Optional[str],
    theme: str,
) -> dict:
    """
    Load the most recent (insight, microstep) for this reflection or theme.

    This lets the Deepen card show persisted AI even after a fresh reload.
    """
    if not (sb and user_id):
        return {}

    try:
        q = (
            sb.table("user_followup_ai")
              .select("insight, microstep")
              .eq("user_id", user_id)
        )
        if reflection_id:
            q = q.eq("reflection_id", reflection_id)
        else:
            # Fallback: last Deepen for this theme
            q = q.eq("theme", (theme or "").strip() or "Reflection")

        res = q.order("created_at", desc=True).limit(1).execute()
        rows = res.data or []
        if not rows:
            return {}
        row = rows[0]
        return {
            "insight": (row.get("insight") or "").strip(),
            "microstep": (row.get("microstep") or "").strip(),
        }
    except Exception:
        return {}




dbg = _get_last_deepen_debug() or {}
silenced_flag = bool(dbg.get("silenced", False))

# ---------------------------------------------------------------------------
# UI building blocks
# ---------------------------------------------------------------------------

def _render_ai_card(
    theme: str,
    insight: str,
    microstep: str,
    dbg: Optional[dict] = None,
) -> None:
    dbg = dbg or {}
    is_silence_flag = bool(dbg.get("silenced", False))

    # Silence-specific copy
    silence_insight = "No words needed. Let the body settle."
    silence_microstep = "Sit upright for ten seconds. Feel one point of contact. Let one exhale pass."

    # Badge (must be defined BEFORE st.markdown f-string)
    silence_badge = (
        '<span class="silence-pill">Silence</span>'
        if is_silence_flag else ""
    )

    silence_subcaption = (
    '<div class="silence-subcaption">Stillness is active.</div>'
    if is_silence_flag else ""
    )

    theme_safe = (theme or "Reflection").strip() or "Reflection"

    dbg = dbg or {}

    is_silenced = bool(dbg.get("silenced", False))
    presence_freshness = dbg.get("presence_freshness")  # inferred upstream
    is_dormant = presence_freshness == "dormant"

    EMPTY_STATE_COPY = "Nothing to add right now. You can stay here."

    insight_clean = (insight or "").strip()
    microstep_clean = (microstep or "").strip()

    # Presence-aware empty state (Silence OR Dormant) + no content
    if (is_silenced or is_dormant) and (not insight_clean) and (not microstep_clean):
        display_insight = EMPTY_STATE_COPY
        display_microstep = ""
    else:
    # Silence mode still overrides when active (first-class)
        display_insight = silence_insight if is_silence_flag else (
            insight_clean
            or "Once you save a deepen note for this reflection, your distilled insight will appear here."
        )

        display_microstep = silence_microstep if is_silence_flag else (
            microstep_clean
            or "A tiny 2-minute action will be suggested here, based on today’s note."
        )

    # Section label shifts tone on silence days
    insight_label = "STILLNESS" if is_silence_flag else "INSIGHT"

    
    theme_block = (
    f'<div class="deepen-ai-card-theme">{theme_safe}</div>'
    if not is_silence_flag else ""
    )

    st.markdown(
    f"""
<div class="deepen-ai-card theme-{theme_safe}">
  <div class="deepen-ai-card-header">
    DEEPEN MENTOR
    {silence_badge}
  </div>
  {silence_subcaption}

  {theme_block}

  <div class="deepen-ai-card-section-label">{insight_label}</div>
  <p>{display_insight}</p>

  <div class="deepen-ai-card-section-label">MICRO-STEP</div>
  <p>{display_microstep}</p>
</div>
""",
    unsafe_allow_html=True,
)
# ---------------------------------------------------------------------------
# Public API — Deepen main panel
# ---------------------------------------------------------------------------

dbg = _get_last_deepen_debug() or {}
is_silence_flag = bool(dbg.get("silenced", False))
silence_reason = dbg.get("silence_reason")

def render_mentor_followup(
    theme: str,
    reflection_text: str,
    row_id: Optional[str] = None,
) -> None:
    """
    Main entry point used by app.py.

    Layout:
      • Left: Deepen note editor + Save button + one-time ribbon
      • Right: latest AI (Insight + Micro-step) in a unified card
      • Below: analytics strip
    """
    _ensure_fu_css()
    sb = _get_sb()
    user_id = st.session_state.get(S_USER_ID)

    theme_label = (theme or "Reflection").strip() or "Reflection"

    # Scope keys per reflection (or theme fallback) to avoid collisions
    scope = row_id or f"theme::{theme_label or 'default'}"
    res_key = f"deepen_ai::{scope}"
    rib_key = f"fu_ribbon::{scope}"
    note_key = f"followup_quick_note::{scope}"

    # ----- Deepen focus theme (user-selectable) -----------------------------
    THEME_CHOICES = [
        "Presence",
        "Clarity",
        "Courage",
        "Compassion",
        "Purpose",
        "Balance",
        "Discipline",
        "Devotion",
        "Surrender",
        "Calm-Sage",
    ]

    theme_key = f"deepen_theme::{scope}"

    # Default to incoming theme if it’s one of our known choices, else Clarity
    default_theme = theme_label if theme_label in THEME_CHOICES else "Clarity"
    selected_theme = st.session_state.get(theme_key, default_theme)

    # Initialise session store for this scope, and hydrate from DB on first load
    if res_key not in st.session_state:
        st.session_state[res_key] = {"insight": "", "microstep": ""}

        stored_db = _load_latest_followup_ai(sb, user_id, row_id, selected_theme)
        if stored_db:
            st.session_state[res_key] = stored_db

    box = st.container(border=True)
    with box:
        st.caption("Mentor follow-up")
        st.subheader("Deepen")

        # Header row: shows the *current Deepen focus* (not the reflection pillar)
        cols = st.columns([2, 2])
        with cols[0]:
            st.markdown(f"**{selected_theme}** — 1 thread • 1 tiny step")
        with cols[1]:
            selected_theme = st.selectbox(
                "Deepen focus",
                THEME_CHOICES,
                index=THEME_CHOICES.index(selected_theme),
                key=theme_key,
            )

        st.caption(
            "Name one intention from this reflection. "
            "Deepen Mentor will mirror it back into a tiny action for today."
        )

        # Context tail line (last line of reflection)
        last_line = (reflection_text or "").strip().splitlines()[-1:] or [""]
        if last_line and last_line[0]:
            st.caption(f"Last note: “{last_line[0]}”")
            st.markdown("<div style='margin-top:-0.1rem'></div>", unsafe_allow_html=True)

        left, right = st.columns([3, 1], gap="large")

        # ----- Left column: editor + save + ribbon -----
        with left:
            note = st.text_area(
                "One-line deepen note (saved)",
                key=note_key,
                height=110,
                placeholder="E.g., “One small thing I want to honour here is…”",
            )
            st.markdown("<div style='margin-top:-0.15rem'></div>", unsafe_allow_html=True)

            subdued_mode = st.checkbox(
            "I feel subdued — keep it ultra-gentle",
            key=f"subdued_mode::{scope}",
            value=False,
            )

            # --- Defaults so we never hit UnboundLocalError ---
            stillness, insight, microstep = "", "", ""
            dbg = {}
            mood = "soft"
            silenced_flag = False
            silence_reason = None
            presence_stage = None

            if silenced_flag:
                st.markdown(
                    '<div class="fu-ribbon">🌿 Silence is holding today. No response is required.</div>',
                    unsafe_allow_html=True,
                )

            if st.button("💾 Save stillness", key=f"save_followup::{scope}"):
                if not sb or not user_id:
                    st.warning("Not signed in or DB unavailable.")
                elif not (note or "").strip():
                    st.warning("Please write a short deepen note before saving.")
                else:
                    try:
                        # 1) Save note onto the reflection (or latest)
                        reflection_id = row_id or _save_followup_note_to_latest(
                            sb,
                            user_id,
                            note or "",
                        )

                        # 2) Gather recent followups (for anti-repeat)
                        recent = _fetch_recent_followups(sb, user_id)

                        # 3) Generate Deepen output (theme_used = selected_theme is our single truth)
                        theme_used = (selected_theme or "Clarity").strip() or "Clarity"

                        stillness, insight, microstep = generate_deepen_insight(
                            theme=theme_used,
                            reflection_text=reflection_text,
                            followup_note=note,
                            recent_followups=recent,
                        )

                        # --- Deepen debug: silence gate inspection (single source of truth) ---
                        dbg = _get_last_deepen_debug() or {}
                        silenced_flag = bool(dbg.get("silenced", False))

                        mood = (dbg.get("mood") or "soft")
                        silence_reason = dbg.get("silence_reason")
                        presence_stage = dbg.get("presence_stage_final") 

                        # Optional UI label
                        st.caption(
                            "Mode: "
                            + ("Silence" if silenced_flag else "Grounded" if dbg.get("subdued") else "Active")
                        )

                        # Keep for UI (optional)
                        st.session_state["deepen_stillness"] = stillness or ""
                        st.session_state["deepen_insight"] = insight or ""
                        st.session_state["deepen_microstep"] = microstep or ""


                        # --- E2: continuity state update (best-effort) ---
                        try:
                            from agi.persistence.state import upsert_reflection_state
                            
                            dbg = _get_last_deepen_debug() or {}
                            is_silence_flag = bool(dbg.get("silenced", False))
                            silence_reason = dbg.get("silence_reason")

                            upsert_reflection_state(
                                supabase=sb,
                                user_id=str(st.session_state.get(S_USER_ID)),
                                theme=theme_used,
                                mood=mood,
                                microstep=(microstep or None),
                                last_meaningful_action="deepen_microstep",
                                silenced=is_silence_flag,
                                silence_reason=silence_reason,
                            )
                        except Exception as e:
                            st.session_state["state_dbg"] = {
                                "enabled": True,
                                "written": False,
                                "error": str(e)[:160],
                            }

                        # Update cached UI card values
                        st.session_state[res_key] = {
                            "insight": insight or "",
                            "microstep": microstep or "",
                        }

                    except Exception as e:
                        st.error(f"Couldn’t generate follow-up: {e}")
                    else:
                        # 4) Save AI result to user_followup_ai
                        ok = _save_followup_ai(
                            sb,
                            user_id=user_id,
                            reflection_id=reflection_id,
                            theme=theme_used,
                            note=note or "",
                            insight=insight,
                            microstep=microstep,
                        )
                        
                        dbg = dbg or {}  # ensure dict

                        # Preferred: trust dbg from generate_deepen_insight (single source of truth)
                        silenced = bool(dbg.get("silenced", False))

                        # Safety fallback: if dbg missing, infer from contract (silence returns insight=None)
                        if "silenced" not in dbg:
                            silenced = (insight is None)

                        if ok:
                            st.session_state[rib_key] = True
                            st.session_state["last_deepen_silenced"] = silenced
                            st.rerun()

            # - Ribbon (shows once, then clears) -
            if st.session_state.get(rib_key):
                silenced = st.session_state.get("last_deepen_silenced", False)

                if silenced:
                    msg = "🪷 Deepen saved. Stillness is active today."
                else:
                    msg = "✅ Deepen saved. A tiny action has been added below."

                st.markdown(
                    f'<div class="fu-ribbon">{msg}</div>',
                    unsafe_allow_html=True,
                )

                st.session_state.pop(rib_key, None)

        # ----- Right column: current AI card (unified pattern) -----

    with right:
        stored = st.session_state.get(res_key, {})

        # single source of truth: always pull latest debug right before render
        dbg = _get_last_deepen_debug() or {}

        # TEMP: keep this caption until you confirm UX is correct
        st.caption(
            f"DBG: silenced={bool(dbg.get('silenced', False))} "
            f"reason={dbg.get('silence_reason')}"
        )

        _render_ai_card(
            selected_theme,
            stored.get("insight", ""),
            stored.get("microstep", ""),
            dbg=dbg,  # <-- critical
        )

        # ----- Analytics strip (theme-aware) -----
        if sb and user_id:
            render_followup_analytics(sb, user_id, theme=selected_theme or None)