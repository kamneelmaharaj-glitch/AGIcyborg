# agi/presence.py
from __future__ import annotations
import math, time
import streamlit as st
from streamlit.components.v1 import html as _html
from .config import PRESENCE_CYCLE_SEC
from .db import insert_presence_session

def render_presence_widget(phase: str | None = None, hint: str | None = None):
    st.markdown(
        f"""
        <div class="presence-wrap">
          <div class="presence-title">
            <span class="dot"></span>
            <span>Return to stillness</span>
            <span class="lotus" style="margin-left:.5rem">🪷</span>
          </div>
          <div class="presence-note">Breathe 4–2–6 and simply notice three sensations.</div>
          <div class="breath-orb"></div>
          <div class="phase">{phase or "Inhale… Exhale…"}</div>
          <div class="sense">{hint or "Notice any touch, temperature, or weight."}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_presence_section(selected_theme: str, sb):
    """Render Presence controls + visuals; handles tone + session tracking."""
    is_presence_theme = (selected_theme == "Presence")
    if not is_presence_theme:
        render_presence_widget()
        st.session_state["presence_was_on"] = False
        st.session_state["presence_autosaved"] = False
        return

    st.markdown("### 🌿 Presence Mode")
    st.caption("Breathe 4–2–6 · Notice · Soften · Receive")
    c1, c2 = st.columns([1, 1])
    with c1:
        st.toggle("Activate Presence Signal", key="presence_signal")
    with c2:
        st.markdown("When active, the orb will pulse gently — stay still for one minute.")

    active = bool(st.session_state.get("presence_signal"))

    if active:
        st.markdown(
            f"""
            <div id="presence-orb" class="presence-orb" style="animation-duration:{PRESENCE_CYCLE_SEC}s"></div>
            <div id="presence-phase" class="presence-phase">Inhale • 4</div>
            """,
            unsafe_allow_html=True,
        )
        _html(
            f"""
            <script>
            (function () {{
              try {{
                if (window.__presenceTimer) {{ clearTimeout(window.__presenceTimer); window.__presenceTimer = null; }}
                const el = parent.document.querySelector("#presence-phase");
                if (!el) return;

                const loopSec = {PRESENCE_CYCLE_SEC};
                const inhale = Math.round(loopSec * (4/12) * 1000);
                const hold   = Math.round(loopSec * (2/12) * 1000);
                const exhale = Math.round(loopSec * (6/12) * 1000);

                const phases = [
                  {{ t: "Inhale • 4", dur: inhale }},
                  {{ t: "Hold • 2",   dur: hold   }},
                  {{ t: "Exhale • 6", dur: exhale }}
                ];
                function tick(i) {{
                  const p = phases[i];
                  el.textContent = p.t;
                  window.__presenceTimer = setTimeout(() => tick((i+1)%phases.length), p.dur);
                }}
                tick(0);
              }} catch (e) {{
                console.error("Presence phase script error:", e);
              }}
            }})();
            </script>
            """,
            height=0,
        )
        _html(
            f"""
            <div id="agi-tone-ui" style="text-align:center;margin-top:.5rem;">
              <button id="agiToneBtn" style="
                padding:.45rem .8rem;border-radius:10px;border:1px solid rgba(255,255,255,.15);
                background:rgba(255,255,255,.06);color:#e6f0ff;font-size:.9rem;cursor:pointer;">
                🔈 Enable tone
              </button>
              <div id="agiToneHint" style="font-size:.8rem;opacity:.7;margin-top:.35rem;">
                Click once to start the breathing tone (required by your browser).
              </div>
            </div>
            <script>
            (function(){{
              if (!window.__agiTone) {{
                window.__agiTone = {{ started:false, killed:false, ctx:null, osc:null, gain:null, loopId:null }};
              }}
              const T = window.__agiTone;
              const LOOP = {PRESENCE_CYCLE_SEC};
              function startTone(){{
                if (T.started) return; T.started = true;
                try {{
                  const AC = window.AudioContext || window.webkitAudioContext;
                  T.ctx = new AC(); T.osc = T.ctx.createOscillator(); T.gain = T.ctx.createGain();
                  T.osc.type = "triangle"; T.osc.frequency.value = 220; T.gain.gain.value = 0.0;
                  T.osc.connect(T.gain).connect(T.ctx.destination);
                  if (T.ctx.state === "suspended") T.ctx.resume();
                  T.osc.start();
                  function scheduleAt(t){{
                    const g = T.gain.gain;
                    const inh=(4/12)*LOOP, hol=(2/12)*LOOP, exh=(6/12)*LOOP;
                    try {{ g.cancelScheduledValues(t); }} catch(e){{}}
                    g.setValueAtTime(0.00, t);
                    g.linearRampToValueAtTime(0.20, t + inh);
                    g.setValueAtTime(0.20, t + inh);
                    g.linearRampToValueAtTime(0.00, t + inh + hol + exh);
                  }}
                  const start = T.ctx.currentTime + 0.05; scheduleAt(start);
                  T.loopId = setInterval(function(){{
                    if (T.killed || !T.ctx) return;
                    const cycles = Math.floor((T.ctx.currentTime - start)/LOOP) + 1;
                    scheduleAt(start + cycles*LOOP);
                  }}, 1500);
                  ["pointerdown","click","touchstart","keydown"].forEach(function(ev){{
                    document.addEventListener(ev, function(){{
                      if (T.ctx && T.ctx.state === "suspended") T.ctx.resume();
                    }}, {{passive:true}});
                  }});
                  var ui = document.getElementById("agi-tone-ui");
                  if (ui) ui.style.display = "none";
                  window.addEventListener("unload", function(){{
                    T.killed = true;
                    try {{ if (T.loopId) clearInterval(T.loopId); }} catch(e){{}}
                    try {{ if (T.osc) T.osc.stop(); }} catch(e){{}}
                  }});
                }} catch (err) {{
                  var hint = document.getElementById("agiToneHint");
                  if (hint) {{
                    hint.textContent = "Tone could not start: " + (err && err.message ? err.message : err);
                    hint.style.opacity = "1";
                  }}
                }}
              }}
              var btn = document.getElementById("agiToneBtn");
              if (btn) btn.addEventListener("click", startTone);
              if (T.started) {{
                var ui = document.getElementById("agi-tone-ui");
                if (ui) ui.style.display = "none";
              }}
            }})();
            </script>
            """,
            height=140,
        )
        st.caption("Notice your breath as light expanding and returning.")
    else:
        render_presence_widget()

    # --- Session logging / autosave (1 min) ---
    now_ts = time.time()
    was_on = bool(st.session_state.get("presence_was_on", False))
    if active and not was_on:
        st.session_state["presence_start_ts"] = now_ts

    def _finalize_presence_session():
        start_ts = st.session_state.get("presence_start_ts")
        if not start_ts: return
        dur = max(0, int(time.time() - start_ts))
        stillness_val = (st.session_state.get("stillness_note") or
                         st.session_state.get("stillness_note_input") or "")
        base = min(1.0, dur / 60.0)
        richness = 0.2 + min(0.8, math.log10(1 + len(stillness_val.strip())) / 1.2)
        presence_score = round(0.5 * base + 0.5 * richness, 3)
        try:
            insert_presence_session(sb, dur, presence_score)
            st.toast(f"Presence session logged — {dur}s · score {presence_score:.2f}")
        except Exception:
            pass
        st.session_state.pop("presence_start_ts", None)

    if active:
        start_ts = st.session_state.get("presence_start_ts")
        if start_ts and (now_ts - start_ts) >= 60 and not st.session_state.get("presence_autosaved"):
            _finalize_presence_session()
            st.session_state["presence_autosaved"] = True
    else:
        if was_on:
            _finalize_presence_session()
        st.session_state["presence_autosaved"] = False

    st.session_state["presence_was_on"] = active

    st.markdown(
        f"""
        <style>
          .presence-orb   {{ animation-duration: {PRESENCE_CYCLE_SEC}s; }}
          .presence-phase {{ margin-top:.4rem; }}
        </style>
        """,
        unsafe_allow_html=True,
    )