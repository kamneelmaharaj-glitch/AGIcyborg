# app.py — AGIcyborg Reflection Space (modular)

from __future__ import annotations
import streamlit as st
import textwrap, random, datetime

from agi.config import init_page, mask
from agi.db import get_client, fetch_prompts, insert_reflection_with_fallbacks
from agi.ai import ai_generate
from agi.presence import render_presence_section
from agi.questions import get_guided_questions, shuffle_guided_questions
from agi.mentor import render_mentor_card
from agi.energy import compute_energy_score, compute_presence_score
from agi.export import build_reflection_markdown
from agi.charts import render_energy_section
from agi.history import render_recent_reflections
from agi.ui import inject_global_css

# ----------------------------
# Boot
# ----------------------------
init_page()
inject_global_css()

st.title("🪷 AGIcyborg Reflection Space")
st.caption("Awakened Guided Intelligence — Your Dharma, Amplified.")

# Supabase
sb = get_client()

# Sidebar diagnostics
with st.sidebar:
    st.markdown("### 🔎 Config")
    from agi.config import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY, OPENAI_API_KEY, OPENAI_PROJECT
    st.write("URL:", mask(SUPABASE_URL))
    st.write("Anon key:", mask(SUPABASE_ANON_KEY))
    st.write("Service key:", mask(SUPABASE_SERVICE_KEY))
    st.write("OpenAI key:", mask(OPENAI_API_KEY))
    st.write("OpenAI project:", OPENAI_PROJECT or "—")
    try:
        chk = sb.table("reflection_prompts").select("id", count="exact").limit(1).execute()
        st.success(f"Prompts OK: {getattr(chk, 'count', None) or '✓'}")
    except Exception as e:
        st.error(f"Prompts check failed: {e}")
    st.divider()

# Load prompts
prompts = fetch_prompts(sb)
if not prompts:
    st.info("No prompts yet. Seed `reflection_prompts` to begin.")
    st.stop()

labels = [
    f"{p['theme']} — {p['prompt'][:72]}{'…' if len(p['prompt']) > 72 else ''}"
    for p in prompts
]
idx = st.session_state.get("prompt_idx", 0)
idx = min(idx, len(prompts) - 1)

sel_idx = st.selectbox(
    "Choose a reflection prompt",
    options=list(range(len(prompts))),
    index=idx,
    format_func=lambda i: labels[i],
    key="prompt_selectbox",
)
st.session_state["prompt_idx"] = sel_idx

selected = prompts[sel_idx]
selected_prompt_id = str(selected["id"])
selected_theme = selected["theme"]
st.session_state["current_theme"] = selected_theme

# Presence (now defined before call, lives in module)
render_presence_section(selected_theme, sb)

# Guided Questions
qs = get_guided_questions(selected_theme, selected_prompt_id, k=3)
used_qs = st.session_state.get(f"used_q::{selected_prompt_id}", set())
if qs:
    st.markdown(f"#### 🪞 Guided Questions for **{selected_theme}**")
    cols = st.columns(min(3, len(qs)))
    for i, q in enumerate(qs):
        is_new = q not in used_qs
        label = f"➕ {q}" if is_new else f"✨ {q}"
        with cols[i % len(cols)]:
            if st.button(label, key=f"gqbtn::{selected_prompt_id}::{i}"):
                prev = st.session_state.get("reflection_text", "")
                st.session_state["reflection_text"] = (prev + ("\n\n" if prev else "") + q + "\n").strip()
                st.rerun()
    if st.button("🔀 Shuffle Questions", key=f"shuffle::{selected_prompt_id}"):
        shuffle_guided_questions(selected_prompt_id)
        st.rerun()

# ----------------------------
# Reflection Form
# ----------------------------
with st.form("reflect_form", clear_on_submit=False):
    with st.container(border=True):
        st.caption("Optional context")
        c1, c2 = st.columns([1, 1])
        with c1:
            mood = st.selectbox(
                "Mood (optional)",
                ["", "Calm", "Focused", "Grateful", "Tender", "Brave", "Curious", "Tired", "Overwhelmed"],
                index=0, key="mood_select",
            )
        with c2:
            tags_raw = st.text_input(
                "Tags (comma-separated, optional)",
                value=st.session_state.get("tags_input", ""),
                placeholder="e.g. work, family, gratitude", key="tags_input",
            )
        stillness_note = st.text_input(
            "Stillness note (optional)",
            value=st.session_state.get("stillness_note_input", ""),
            placeholder="A small body-sense you noticed (breath, warmth, ground, etc.)",
            key="stillness_note_input",
        )

    reflection_text = st.text_area(
        "Your Reflection",
        value=st.session_state.get("reflection_text", ""),
        height=180,
        placeholder="Write honestly. Small and true is enough.",
        key="reflection_text",
    )

    use_ai = st.checkbox("Generate Mentor Insight + Mantra (OpenAI)", value=True, key="use_ai")
    submitted = st.form_submit_button("Submit", type="primary")

# Track used guided questions
used_key = f"used_q::{selected_prompt_id}"
if st.session_state.get("reflection_text", "").strip():
    prev_used = st.session_state.get(used_key, set())
    new_used = prev_used.union(set(st.session_state["reflection_text"].splitlines()))
    st.session_state[used_key] = new_used

st.session_state["tags_raw"] = st.session_state.get("tags_input", "")
st.session_state["mood"] = st.session_state.get("mood_select") or ""
st.session_state["stillness_note"] = st.session_state.get("stillness_note_input", "")

# Submit handler
if submitted:
    if not reflection_text.strip():
        st.warning("Please enter a reflection before submitting.")
    else:
        generated_insight, generated_mantra = None, None
        theme_used = st.session_state.get("current_theme", selected_theme)
        if use_ai:
            try:
                with st.spinner("Invoking Mentor…"):
                    generated_insight, generated_mantra = ai_generate(theme_used, reflection_text)
            except Exception as e:
                st.warning(f"AI generation skipped: {e}")

        base_row = {
            "prompt_id": selected_prompt_id,
            "theme": theme_used,
            "reflection_text": reflection_text.strip(),
            "generated_insight": generated_insight,
            "generated_mantra": generated_mantra,
        }
        raw_csv   = (st.session_state.get("tags_raw") or "").strip()
        tags_list = [t.strip() for t in raw_csv.split(",") if t.strip()]
        mood_val      = st.session_state.get("mood") or None
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

        ins = insert_reflection_with_fallbacks(sb, base_row, optional_fields, energy_fields)
        try:
            if getattr(ins, "data", None):
                st.session_state["last_row_id"] = ins.data[0].get("id")
        except Exception:
            pass

        st.session_state["last_reflection"] = reflection_text.strip()
        st.session_state["last_theme"] = theme_used
        st.session_state["last_mentor"] = {"theme": theme_used, "insight": generated_insight or "", "mantra": generated_mantra or ""}
        st.session_state["clear_reflection"] = True
        st.success("Reflection saved. Thank you.")
        st.rerun()

# Persisted mentor card + download
_last = st.session_state.get("last_mentor")
if _last and (_last.get("insight") or _last.get("mantra")):
    render_mentor_card(_last.get("theme","Clarity"), _last.get("insight",""), _last.get("mantra",""), anchor_id="mentor_card_last")
    if st.button("Dismiss guidance", key="dismiss_last_mentor"):
        st.session_state.pop("last_mentor", None); st.rerun()

# Download MD
if _last and (_last.get("insight") or _last.get("mantra")):
    md_text = build_reflection_markdown(
        created_at=None,
        theme=_last.get("theme",""),
        reflection=st.session_state.get("last_reflection",""),
        insight=_last.get("insight",""),
        mantra=_last.get("mantra",""),
        tags=[t.strip() for t in st.session_state.get("tags_raw","").split(",") if t.strip()],
        mood=st.session_state.get("mood"),
        stillness_note=st.session_state.get("stillness_note"),
    )
    st.download_button("⬇️ Download as Markdown", data=md_text.encode("utf-8"), file_name="reflection.md", mime="text/markdown", key="dl_md_last")

# Regenerate guidance
st.markdown("---")
st.subheader("✨ Refine Mentor Guidance")
theme_for_regen = (st.session_state.get("last_theme") or st.session_state.get("current_theme") or selected_theme)
regen_reflection = st.text_area("Use your last reflection (or paste a new one) to regenerate guidance.",
                                value=st.session_state.get("last_reflection",""),
                                height=140, key="regen_text")
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
    render_mentor_card(theme_for_regen,
                       st.session_state.get("regen_insight"),
                       st.session_state.get("regen_mantra"),
                       anchor_id="mentor_card_regen")
    if st.button("Save this regenerated guidance"):
        try:
            sb.table("user_reflections").insert({
                "prompt_id": selected_prompt_id,
                "theme": theme_for_regen,
                "reflection_text": regen_reflection.strip(),
                "generated_insight": st.session_state.get("regen_insight"),
                "generated_mantra": st.session_state.get("regen_mantra"),
            }).execute()
            st.success("Regenerated guidance saved.")
        except Exception as e:
            st.error(f"Save failed: {e}")

# Energy + History
from agi.charts import render_energy_section
render_energy_section(sb, days=45)

from agi.history import render_recent_reflections
render_recent_reflections(sb)