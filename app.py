# app.py — AGIcyborg Reflection Space (modular)

from __future__ import annotations
import streamlit as st
import textwrap, random, datetime
from agi.deepen_ai import generate_deepen_insight

# ----------------------------
# Page / config (must be first)
# ----------------------------
from agi.config import init_page, mask, mask_url
init_page()

# ----------------------------
# Core deps
# ----------------------------
from agi.db import get_client, fetch_prompts, insert_reflection_with_fallbacks
from agi.auth import auth_gate, S_USER_ID
from agi.metrics import render_user_metrics

from agi.ai import ai_generate
from agi.presence import render_presence_section
from agi.questions import (
    get_guided_questions,
    shuffle_guided_questions,
    get_theme_blurb,
)
from agi.mentor import render_mentor_card
from agi.energy import compute_energy_score, compute_presence_score
from agi.export import build_reflection_markdown
from agi.charts import render_energy_section
from agi.history import render_recent_reflections, render_presence_continuity
from agi.ui import inject_global_css
from agi.mirror import render_mirror_panel
from agi.journal_ai import build_journal_insight, render_journal_insight
from agi.followup import render_mentor_followup, render_microstep_widget, render_today_panel
from agi.reflection_ui import render_reflection_header
from agi.debug import render_debug_panel

import os

def _is_set(v: str | None) -> bool:
    return bool((v or "").strip())

def _last4(v: str | None) -> str:
    s = (v or "").strip()
    return ("…" + s[-4:]) if len(s) >= 4 else "—"

def _safe_secret_label(v: str | None, *, name: str) -> str:
    if not _is_set(v):
        return f"{name}: —"
    return f"{name}: set ({_last4(v)})"

# ----------------------------
# Boot
# ----------------------------
inject_global_css()

# Supabase client + auth gate
sb = get_client()
# Expose sb for modules (e.g., followup.py uses session "sb")
st.session_state["sb"] = sb

user_id = auth_gate(sb)
if not user_id:
    st.stop()

# Debug panel (safe location)
render_debug_panel(sb)

# ----------------------------
# Load prompts ONCE
# ----------------------------
prompts = fetch_prompts(sb)
if not prompts:
    st.warning("⚠️ No prompts found in Supabase. Please seed the `reflection_prompts` table.")
    st.stop()

# ----------------------------
# Header
# ----------------------------
st.title("🪷 AGIcyborg Reflection Space")
st.caption("Awakened Guided Intelligence — Your Dharma, Amplified.")

# ----------------------------
# Filters (define BEFORE using them anywhere)
# ----------------------------
RANGE_CHOICES = {"7 days": 7, "14 days": 14, "30 days": 30, "90 days": 90}
c1, c2 = st.columns([1, 1])

with c1:
    range_label = st.selectbox(
        "Range",
        list(RANGE_CHOICES.keys()),
        index=2,                # default: 30 days
        key="flt_range_choice"
    )
    flt_days = RANGE_CHOICES[range_label]

with c2:
    theme_list = ["All"] + sorted({p.get("theme", "") for p in prompts if p.get("theme")})
    theme_choice = st.selectbox(
        "Theme",
        theme_list,
        index=0,
        key="flt_theme_choice"
    )
    flt_theme = None if theme_choice == "All" else theme_choice

# Persist derived values (optional but handy)
st.session_state["flt_days_value"] = flt_days
st.session_state["flt_theme_value"] = flt_theme

st.markdown("---")

# ----------------------------
# Sidebar diagnostics
# ----------------------------
with st.sidebar:
    st.markdown("### 🔎 Config")
    from agi.config import (
        SUPABASE_URL,
        SUPABASE_ANON_KEY,
        SUPABASE_SERVICE_KEY,
        OPENAI_API_KEY,
        OPENAI_PROJECT,
    )
    st.write("URL:", mask_url(SUPABASE_URL))

    st.write(_safe_secret_label(SUPABASE_ANON_KEY, name="Anon key"))
    st.write(_safe_secret_label(SUPABASE_SERVICE_KEY, name="Service key"))
    st.write(_safe_secret_label(OPENAI_API_KEY, name="OpenAI key"))

    # Project is not a secret (usually), OK to show:
    st.write("OpenAI project:", OPENAI_PROJECT or "—")
    try:
        chk = sb.table("reflection_prompts").select("id", count="exact").limit(1).execute()
        st.success(f"Prompts OK: {getattr(chk, 'count', None) or '✓'}")
    except Exception as e:
        st.error(f"Prompts check failed: {e}")
    st.divider()
    

# ----------------------------
# Personalized metrics (now that filters exist)
# ----------------------------
render_user_metrics(sb, user_id, days=flt_days, theme=flt_theme)

# ----------------------------
# Prompt selection (with 7-day follow-up badges)
# ----------------------------

# --- Prompt label helper (no external theme-count helper needed) ---
def _prompt_label(i: int) -> str:
    p = prompts[i]
    theme = p["theme"]
    snippet = p["prompt"][:72] + ("…" if len(p["prompt"]) > 72 else "")
    return f"{theme} — {snippet}"

# Remember last prompt (for detecting changes)
prev_prompt_id = st.session_state.get("current_prompt_id")

idx = st.session_state.get("prompt_idx", 0)
idx = min(idx, len(prompts) - 1)

sel_idx = st.selectbox(
    "Choose a reflection prompt",
    options=list(range(len(prompts))),
    index=idx,
    format_func=_prompt_label,
    key="prompt_selectbox",
)
st.session_state["prompt_idx"] = sel_idx

selected = prompts[sel_idx]
selected_prompt_id = str(selected["id"])
selected_theme = selected["theme"]
st.session_state["current_theme"] = selected_theme

# 🔹 If the prompt changed, clear the reflection draft + local context
if prev_prompt_id and prev_prompt_id != selected_prompt_id:
    for k in [
        "reflection_text",
        "reflection_mood",
        "reflection_tags",
        "reflection_stillness",
    ]:
        st.session_state.pop(k, None)
    # Clear the used guided-question set for the *new* prompt
    st.session_state[f"used_q::{selected_prompt_id}"] = set()

st.session_state["current_prompt_id"] = selected_prompt_id

# ----------------------------
# Today’s micro-step card
# ----------------------------

selected = prompts[sel_idx]
selected_prompt_id = str(selected["id"])
selected_theme = selected["theme"]
st.session_state["current_theme"] = selected_theme

# Ensure reflection_text exists in session state
if "reflection_text" not in st.session_state:
    st.session_state["reflection_text"] = ""

# ----------------------------
# Guided Questions
# ----------------------------

# Fetch a fresh set from the helper for this theme + prompt
base_qs = get_guided_questions(selected_theme, selected_prompt_id, k=3) or []

# Keys to keep per-prompt state
bank_key = f"guided_bank::{selected_prompt_id}"
used_key = f"used_q::{selected_prompt_id}"

# 1) Initialise the bank the first time we see this prompt
if bank_key not in st.session_state:
    st.session_state[bank_key] = list(base_qs)

# 2) If the bank somehow became empty, repopulate from base_qs
if not st.session_state[bank_key] and base_qs:
    st.session_state[bank_key] = list(base_qs)

qs = list(st.session_state[bank_key] or [])
used_qs = st.session_state.get(used_key, set())

# Nicely formatted theme label
theme_label = selected_theme or "Reflection"

# Header row with shuffle button + tiny legend
hdr_left, hdr_right = st.columns([5, 1])
with hdr_left:
    st.markdown(f"### 🪞 Guided questions for **{theme_label}**")
    st.caption(
        "Tap a question to send it into your reflection box. "
        "New questions are marked 🆕, ones you've used before are marked ↺."
    )
with hdr_right:
    if st.button(
        "⟳ Shuffle",
        key=f"shuffle::{selected_prompt_id}",
        help="Try different questions",
    ):
        bank = list(st.session_state.get(bank_key, base_qs))
        if bank:
            import random

            random.shuffle(bank)
            st.session_state[bank_key] = bank
        st.rerun()

# Pull the current ordered list after any shuffle
qs = list(st.session_state.get(bank_key, base_qs) or [])

if qs:
    cols = st.columns(min(3, len(qs)))
    for i, q in enumerate(qs):
        is_new = q not in used_qs

        # Badge prefix depending on whether we've used this question already
        prefix = "🆕 " if is_new else "↺ "
        label = prefix + q

        with cols[i % len(cols)]:
            if st.button(label, key=f"gqbtn::{selected_prompt_id}::{i}"):
                prev = st.session_state.get("reflection_text", "")

                # Nicely formatted insertion block:
                question_block = f"Q: {q}\n\n"

                # If there is already text and it doesn't end with a blank line,
                # add one to separate sections.
                if prev and not prev.endswith("\n\n"):
                    prev = prev.rstrip() + "\n\n"

                st.session_state["reflection_text"] = (prev + question_block).rstrip()

                # Mark this question as used so we can style it differently
                used_qs.add(q)
                st.session_state[used_key] = used_qs

                st.rerun()
else:
    st.caption("No guided questions available for this prompt yet.")

# ---- Handle deferred clear before any widgets are created ----
if st.session_state.get("_request_clear_reflection"):
    st.session_state["_request_clear_reflection"] = False

    # Reset both logical + widget-facing keys
    st.session_state["reflection_text"] = ""
    st.session_state["reflection_box"] = ""

    # Reset context fields
    st.session_state["tags_raw"] = ""
    st.session_state["mood"] = ""
    st.session_state["stillness_note"] = ""

# --- Today (subtle + collapsed) ---
with st.expander("Today", expanded=False):
    render_today_panel(sb, user_id)

# ----------------------------
# Reflection Form
# ----------------------------
with st.expander("Prompt", expanded=False):
    render_reflection_header(
        selected_theme,
        selected.get("prompt", ""),
    )

# Ensure the logical key exists
if "reflection_text" not in st.session_state:
    st.session_state["reflection_text"] = ""

with st.form("reflect_form", clear_on_submit=False):
    with st.container(border=True):
        st.caption("Optional context")

        c1, c2 = st.columns([1, 1])

        # Mood
        with c1:
            mood = st.selectbox(
                "Mood (optional)",
                ["", "Calm", "Focused", "Grateful", "Tender",
                 "Brave", "Curious", "Tired", "Overwhelmed"],
                index=0,
                key="mood_select",
            )

        # Tags
        with c2:
            tags_raw = st.text_input(
                "Tags (comma-separated, optional)",
                value=st.session_state.get("tags_raw", ""),
                placeholder="e.g. work, family, gratitude",
                key="tags_input",
            )

        # Stillness note
        stillness_note = st.text_input(
            "Stillness note (optional)",
            value=st.session_state.get("stillness_note", ""),
            placeholder="A small body-sense you noticed (breath, warmth, ground, etc.)",
            key="stillness_note_input",
        )

        # Mirror widget values into logical keys
        st.session_state["mood"] = mood
        st.session_state["tags_raw"] = tags_raw
        st.session_state["stillness_note"] = stillness_note

        # ---- Your Reflection ----
        st.markdown("#### Your Reflection")

        st.markdown(
            """
            <div class="reflection-helper">
                Tip: Click any guided question above to drop it into this box,
                then write your answer underneath it in your own words.
            </div>
            """,
            unsafe_allow_html=True,
        )

        # SINGLE source of truth: key="reflection_text"
        reflection_text = st.text_area(
            "Reflection",  # must be non-empty
            height=260,
            placeholder="Write honestly. Small and true is enough.",
            key="reflection_text",
            label_visibility="collapsed",
        )

        # Mentor toggle
        generate_insight = st.checkbox(
            "Generate Mentor Insight + Mantra (OpenAI)",
            value=True,
            key="use_ai",
        )

    # Buttons inside the form
    col_submit, col_clear = st.columns([4, 1])
    with col_submit:
        submitted = st.form_submit_button("Save Reflection")
    with col_clear:
        cleared = st.form_submit_button("Begin Again", type="secondary")

# ---- Clear handler ----
if cleared:
    # Don’t touch widget keys directly here – just request a clear
    st.session_state["_request_clear_reflection"] = True
    st.session_state[f"used_q::{selected_prompt_id}"] = set()
    st.rerun()

# ----------------------------
# Submit handler (DROP-IN)
# ----------------------------
if submitted:
    # 1) Read exactly what the user typed
    raw_reflection = (st.session_state.get("reflection_text") or "")

    # 2) Validate BEFORE sanitizing
    if not raw_reflection.strip():
        st.warning("Please enter a reflection before submitting.")
        st.stop()

    # 3) Sanitize out old debug HTML that may be in stored reflections
    cleaned_lines = []
    for line in raw_reflection.splitlines():
        s = line.strip()

        # keep blank lines so spacing feels natural
        if not s:
            cleaned_lines.append(line)
            continue

        # old Mirror debug block lines – strip entirely
        if "mirror-last-mentor" in s:
            continue
        if "Mentor:" in s and "<span" in s:
            continue

        # any pure tag line like <div ...> or </div>
        if s.startswith("<") and s.endswith(">"):
            continue

        cleaned_lines.append(line)

    reflection_text = "\n".join(cleaned_lines).strip()

    # If sanitisation wiped everything, block submission
    if not reflection_text:
        st.warning("Reflection contains no meaningful content after cleanup.")
        st.stop()

    # IMPORTANT: do NOT write back into st.session_state["reflection_text"] here

    # Theme resolution (robust)
    theme_used = (
        (st.session_state.get("current_theme") or "").strip()
        or (st.session_state.get("last_theme") or "").strip()
        or (selected_theme or "").strip()
        or "Clarity"
    )

    generated_insight, generated_mantra = None, None

    if generate_insight:
        try:
            with st.spinner("Invoking Mentor…"):
                generated_insight, generated_mantra = ai_generate(theme_used, reflection_text)
        except Exception as e:
            st.warning(f"AI generation skipped: {e}")

    base_row = {
        "prompt_id":         selected_prompt_id,
        "theme":             theme_used,
        "reflection_text":   reflection_text,
        "generated_insight": generated_insight,
        "generated_mantra":  generated_mantra,
    }

    raw_csv       = (st.session_state.get("tags_raw") or "").strip()
    tags_list     = [t.strip() for t in raw_csv.split(",") if t.strip()]
    mood_val      = (st.session_state.get("mood") or None)
    stillness_val = (st.session_state.get("stillness_note") or "").strip() or None

    optional_fields = {
        "mood":           mood_val,
        "stillness_note": stillness_val,
        "tags":           tags_list or None,
        "tags_raw":       raw_csv or None,
        "source":         "app",
    }

    try:
        energy_score   = compute_energy_score(mood_val, reflection_text)
        presence_score = compute_presence_score(stillness_val)
    except Exception:
        energy_score, presence_score = None, None

    energy_fields = {
        "energy_score":   energy_score,
        "presence_score": presence_score,
    }

    # Write reflection row
    ins = insert_reflection_with_fallbacks(
        sb,
        base_row,
        optional_fields,
        energy_fields,
        user_id=st.session_state.get(S_USER_ID),
    )

    # Mirror-mode vector update (best-effort)
    try:
        from agi.db import upsert_reflection_vector
        upsert_reflection_vector(
            sb,
            user_id=st.session_state.get(S_USER_ID),
            theme=theme_used,
            energy=energy_score,
            presence=presence_score,
        )
    except Exception:
        pass

    # Persist “last” state for post-submit UI
    try:
        if getattr(ins, "data", None) and len(ins.data):
            st.session_state["last_row_id"] = ins.data[0].get("id")
    except Exception:
        pass

    st.session_state["last_reflection"] = reflection_text
    st.session_state["last_theme"]      = theme_used
    st.session_state["last_mentor"]     = {
        "theme":   theme_used,
        "insight": generated_insight or "",
        "mantra":  generated_mantra or "",
    }

    ji = build_journal_insight(
        reflection_text,
        energy_score=energy_score,
        presence_score=presence_score,
    )
    st.session_state["last_journal_ai"] = ji

    # NOTE: Option C "single writer" — do NOT write reflection_state here.
    # Reflection_state is synced from E1 events (reflection_memory) after successful insert.
    # Keep submit lightweight + UI-safe.

    st.session_state["just_saved"] = True
    st.success("Reflection saved. Thank you.")
    st.rerun()
# ----------------------------
# Persisted mentor card + download
# ----------------------------
_last = st.session_state.get("last_mentor")
if _last and (_last.get("insight") or _last.get("mantra")):
    render_mentor_card(
        _last.get("theme", "Clarity"),
        _last.get("insight", ""),
        _last.get("mantra", ""),
        anchor_id="mentor_card_last",
    )
    if st.button("Dismiss guidance", key="dismiss_last_mentor"):
        st.session_state.pop("last_mentor", None)
        st.rerun()

if _last and (_last.get("insight") or _last.get("mantra")):
    md_text = build_reflection_markdown(
        created_at=None,
        theme=_last.get("theme", ""),
        reflection=st.session_state.get("last_reflection", ""),
        insight=_last.get("insight", ""),
        mantra=_last.get("mantra", ""),
        tags=[t.strip() for t in st.session_state.get("tags_raw", "").split(",") if t.strip()],
        mood=st.session_state.get("mood"),
        stillness_note=st.session_state.get("stillness_note"),
    )
    st.download_button(
        "⬇️ Download as Markdown",
        data=md_text.encode("utf-8"),
        file_name="reflection.md",
        mime="text/markdown",
        key="dl_md_last",
    )

# --- Reflective Mind card (appears after submit) ---
if st.session_state.get("last_journal_ai"):
    render_journal_insight(st.session_state["last_journal_ai"])

# --- Mentor Follow-up (appears once after a successful save) ---
from agi.followup import render_mentor_followup

last_id = st.session_state.get("last_row_id")
last_reflection = st.session_state.get("last_reflection")
last_theme = st.session_state.get("last_theme")

if last_id and last_reflection:
    render_mentor_followup(
        theme=last_theme or "Reflection",
        reflection_text=last_reflection,
        row_id=str(last_id),  # ensures DB linkage + unique widget keys
    )

# ----------------------------
# Theme patterns (last 3–5 reflections)
# ----------------------------
from collections import Counter
from statistics import mean

def render_theme_patterns(sb, user_id: str, theme: str | None):
    """Show subtle patterns from the last few reflections for this theme."""
    if not theme:
        return

    try:
        res = (
            sb.table("user_reflections")
            .select(
                "created_at, mood, tags, tags_raw, energy_score, presence_score"
            )
            .eq("user_id", user_id)
            .eq("theme", theme)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
    except Exception as e:
        st.debug(f"pattern fetch failed: {e}")
        return

    rows = getattr(res, "data", None) or []
    if len(rows) < 3:
        with st.expander(f"Subtle patterns in your recent **{theme}** reflections", expanded=False):
            st.caption("Patterns will start to appear once you have at least 3 reflections for this theme.")
        return

    moods = [r.get("mood") for r in rows if r.get("mood")]
    tags_flat = []
    for r in rows:
        if isinstance(r.get("tags"), list):
            tags_flat.extend([t for t in r["tags"] if isinstance(t, str)])
        raw = (r.get("tags_raw") or "").strip()
        if raw:
            tags_flat.extend([t.strip() for t in raw.split(",") if t.strip()])

    energy_vals = [r["energy_score"] for r in rows if r.get("energy_score") is not None]
    presence_vals = [r["presence_score"] for r in rows if r.get("presence_score") is not None]

    mood_summary = None
    if moods:
        c = Counter(moods)
        top_mood, top_mood_count = c.most_common(1)[0]
        mood_summary = (top_mood, top_mood_count, len(moods))

    tags_summary = None
    if tags_flat:
        c = Counter(tags_flat)
        tags_summary = [t for t, _ in c.most_common(3)]

    avg_energy = mean(energy_vals) if energy_vals else None
    avg_presence = mean(presence_vals) if presence_vals else None

    with st.expander(f"Subtle patterns in your recent **{theme}** reflections", expanded=False):
        st.caption("Looking at your last few reflections for this theme:")
        bullets = []

        if mood_summary:
            top_mood, count, total = mood_summary
            bullets.append(
                f"• Your mood has most often been **{top_mood}** ({count} out of {total})."
            )

        if tags_summary:
            tags_str = ", ".join(f"`{t}`" for t in tags_summary)
            bullets.append(f"• Themes that keep showing up: {tags_str}.")

        if avg_energy is not None:
            bullets.append(f"• Your **energy score** is around **{avg_energy:.1f}**.")
        if avg_presence is not None:
            bullets.append(f"• Your **presence score** is around **{avg_presence:.1f}**.")

        if not bullets:
            st.write("No clear patterns yet. Keep reflecting and they’ll appear.")
        else:
            for line in bullets:
                st.write(line)

        st.caption("Let this be gentle information, not judgment.")
# ----------------------------
# Theme-level subtle patterns
# ----------------------------
theme_for_patterns = (
    st.session_state.get("last_theme")
    or st.session_state.get("current_theme")
    or selected_theme
)

with st.expander("Subtle Patterns", expanded=False):
    render_theme_patterns(sb, user_id, theme_for_patterns)

# ----------------------------
# Regenerate guidance
# ----------------------------
st.markdown("---")
with st.expander("Refine Guidance", expanded=False):
    # entire regen block

    theme_for_regen = (
        st.session_state.get("last_theme")
        or st.session_state.get("current_theme")
        or selected_theme
)

regen_reflection = st.text_area(
    "Use your last reflection (or paste a new one) to regenerate guidance.",
    value=st.session_state.get("last_reflection", ""),
    height=140,
    key="regen_text",
)

if st.button("Regenerate Insight (won’t save automatically)"):
    if not regen_reflection.strip():
        st.warning("Please enter text to regenerate.")
    else:
        try:
            with st.spinner("Re-centering…"):
                r_insight, r_mantra = ai_generate(theme_for_regen, regen_reflection)
            st.session_state["regen_insight"] = r_insight
            st.session_state["regen_mantra"]  = r_mantra
        except Exception as e:
            st.error(f"Regeneration failed: {e}")

if st.session_state.get("regen_insight") or st.session_state.get("regen_mantra"):
    render_mentor_card(
        theme_for_regen,
        st.session_state.get("regen_insight"),
        st.session_state.get("regen_mantra"),
        anchor_id="mentor_card_regen",
    )
    if st.button("Save this regenerated guidance"):
        try:
            sb.table("user_reflections").insert({
                "prompt_id": selected_prompt_id,
                "theme": theme_for_regen,
                "reflection_text": regen_reflection.strip(),
                "generated_insight": st.session_state.get("regen_insight"),
                "generated_mantra": st.session_state.get("regen_mantra"),
                "user_id": st.session_state.get(S_USER_ID),
            }).execute()
            st.success("Regenerated guidance saved.")
        except Exception as e:
            st.error(f"Save failed: {e}")


# ----------------------------
# Energy + History (use the SAME filters)
# ----------------------------
with st.expander("Energy & Reflection History", expanded=False):
    render_energy_section(sb, days=flt_days, theme=flt_theme)
    render_presence_continuity(sb, limit=7)
    render_recent_reflections(sb, days=flt_days, theme=flt_theme)