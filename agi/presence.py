# agi/presence.py
from __future__ import annotations

import math
import time

import streamlit as st
from streamlit.components.v1 import html as _html

from .config import PRESENCE_CYCLE_SEC
from .db import insert_presence_session
from .auth import S_USER_ID

# Single global key that other panels (e.g. Today panel) can read
PRESENCE_TOGGLE_KEY = "presence_toggle_global"


def render_presence_widget(phase: str | None = None, hint: str | None = None) -> None:
    """Simple static presence widget used when Presence mode is off."""
    st.markdown(
        """
        <div class="presence-wrap">
          <div class="presence-title">
            <span class="dot"></span>
            <span>Return to stillness</span>
            <span class="lotus" style="margin-left:.5rem">🪷</span>
          </div>
          <div class="presence-note">
            Breathe 4–2–6 and simply notice three sensations.
          </div>
          <div class="breath-orb"></div>
          <div class="phase">{phase}</div>
          <div class="sense">
            {hint}
          </div>
        </div>
        """.format(
            phase=phase or "Inhale… Exhale…",
            hint=hint or "Notice any touch, temperature, or weight.",
        ),
        unsafe_allow_html=True,
    )


def render_presence_section(selected_theme: str, sb) -> None:
    """
    Render the dedicated Presence Mode panel.

    Behaviour:
      • Only shows when the current theme is exactly "Presence".
      • Uses one global toggle key (PRESENCE_TOGGLE_KEY) for on/off state.
      • When active, shows animated orb + optional tone.
      • Logs a presence session after 60s, or when you turn it off.
    """

    # Only show this panel for the Presence theme
    is_presence_theme = selected_theme == "Presence"
    if not is_presence_theme:
        # We’re not in Presence mode; clear any running session state
        st.session_state["presence_was_on"] = False
        st.session_state.pop("presence_start_ts", None)
        st.session_state["presence_autosaved"] = False
        return

    # --- Header ---
    st.markdown("### 🌿 Presence Mode")
    st.caption("Breathe 4–2–6 · Notice · Soften · Receive")

    # --- Toggle row ---
    c1, c2 = st.columns([1, 1])
    with c1:
        st.toggle(
            "Activate Presence Signal",
            key=PRESENCE_TOGGLE_KEY,
            value=st.session_state.get(PRESENCE_TOGGLE_KEY, False),
        )
    with c2:
        st.markdown(
            "When active, the orb will pulse gently — stay still for one minute."
        )

    # Single source of truth for Presence Mode ON/OFF
    active = bool(st.session_state.get(PRESENCE_TOGGLE_KEY, False))

    # ------------------------------------------------------------------
    # Orb + phase / tone UI
    # ------------------------------------------------------------------
    if active:
        # Orb container + phase label
        st.markdown(
            """
            <div id="presence-orb" class="presence-orb"></div>
            <div id="presence-phase" class="presence-phase">Inhale • 4</div>
            """,
            unsafe_allow_html=True,
        )

        # JS loop for the 4–2–6 text phases
        js_phase = """
        <script>
        (function () {{
          try {{
            if (window.__presenceTimer) {{
              clearTimeout(window.__presenceTimer);
              window.__presenceTimer = null;
            }}

            const el = parent.document.querySelector("#presence-phase");
            if (!el) return;

            const loopSec = {loop_sec};
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
              window.__presenceTimer = setTimeout(
                function () {{ tick((i+1) % phases.length); }},
                p.dur
              );
            }}

            tick(0);
          }} catch (e) {{
            console.error("Presence phase script error:", e);
          }}
        }})();
        </script>
        """.format(loop_sec=PRESENCE_CYCLE_SEC)

        _html(js_phase, height=0)

        # Optional tone UI
        js_tone = """
        <div id="agi-tone-ui" style="text-align:center;margin-top:.5rem;">
          <button id="agiToneBtn" style="
            padding:.45rem .8rem;
            border-radius:10px;
            border:1px solid rgba(255,255,255,.15);
            background:rgba(255,255,255,.06);
            color:#e6f0ff;
            font-size:.9rem;
            cursor:pointer;">
            🔈 Enable tone
          </button>
          <div id="agiToneHint" style="font-size:.8rem;opacity:.7;margin-top:.35rem;">
            Click once to start the breathing tone (required by your browser).
          </div>
        </div>
        <script>
        (function() {{
          if (!window.__agiTone) {{
            window.__agiTone = {{
              started:false, killed:false,
              ctx:null, osc:null, gain:null, loopId:null
            }};
          }}

          const T = window.__agiTone;
          const LOOP = {loop_sec};

          function startTone() {{
            if (T.started) return;
            T.started = true;
            try {{
              const AC = window.AudioContext || window.webkitAudioContext;
              T.ctx = new AC();
              T.osc = T.ctx.createOscillator();
              T.gain = T.ctx.createGain();

              T.osc.type = "triangle";
              T.osc.frequency.value = 220;
              T.gain.gain.value = 0.0;
              T.osc.connect(T.gain).connect(T.ctx.destination);

              if (T.ctx.state === "suspended") T.ctx.resume();
              T.osc.start();

              function scheduleAt(t) {{
                const g = T.gain.gain;
                const inh = (4/12)*LOOP;
                const hol = (2/12)*LOOP;
                const exh = (6/12)*LOOP;
                try {{ g.cancelScheduledValues(t); }} catch(e) {{}}
                g.setValueAtTime(0.00, t);
                g.linearRampToValueAtTime(0.20, t + inh);
                g.setValueAtTime(0.20, t + inh);
                g.linearRampToValueAtTime(0.00, t + inh + hol + exh);
              }}

              const start = T.ctx.currentTime + 0.05;
              scheduleAt(start);

              T.loopId = setInterval(function() {{
                if (T.killed || !T.ctx) return;
                const cycles = Math.floor((T.ctx.currentTime - start)/LOOP) + 1;
                scheduleAt(start + cycles*LOOP);
              }}, 1500);

              ["pointerdown","click","touchstart","keydown"].forEach(function(ev) {{
                document.addEventListener(ev, function() {{
                  if (T.ctx && T.ctx.state === "suspended") T.ctx.resume();
                }}, {{passive:true}});
              }});

              var ui = document.getElementById("agi-tone-ui");
              if (ui) ui.style.display = "none";

              window.addEventListener("unload", function() {{
                T.killed = true;
                try {{ if (T.loopId) clearInterval(T.loopId); }} catch(e) {{}}
                try {{ if (T.osc) T.osc.stop(); }} catch(e) {{}}
              }});
            }} catch (err) {{
              var hint = document.getElementById("agiToneHint");
              if (hint) {{
                hint.textContent = "Tone could not start: " +
                  (err && err.message ? err.message : err);
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
        """.format(loop_sec=PRESENCE_CYCLE_SEC)

        _html(js_tone, height=140)

        st.caption("Notice your breath as light expanding and returning.")
    else:
        # Presence not active but theme *is* Presence → show simple static widget.
        render_presence_widget()

    # ------------------------------------------------------------------
    # Session logging / autosave (1 min)
    # ------------------------------------------------------------------
    now_ts = time.time()
    was_on = bool(st.session_state.get("presence_was_on", False))

    # When we flip from OFF → ON, capture start time
    if active and not was_on:
        st.session_state["presence_start_ts"] = now_ts

    def _finalize_presence_session() -> None:
        start_ts = st.session_state.get("presence_start_ts")
        if not start_ts:
            return

        dur = max(0, int(time.time() - start_ts))

        stillness_val = (
            st.session_state.get("stillness_note")
            or st.session_state.get("stillness_note_input")
            or ""
        )

        base = min(1.0, dur / 60.0)
        richness = 0.2 + min(
            0.8, math.log10(1 + len(stillness_val.strip())) / 1.2
        )
        presence_score = round(0.5 * base + 0.5 * richness, 3)

        try:
            insert_presence_session(
                sb, dur, presence_score, st.session_state.get(S_USER_ID)
            )
            st.toast(
                f"Presence session logged — {dur}s · score {presence_score:.2f}"
            )
        except Exception:
            # Silent failure is OK here; this is “nice to have”
            pass

        st.session_state.pop("presence_start_ts", None)

    if active:
        start_ts = st.session_state.get("presence_start_ts")
        autosaved = st.session_state.get("presence_autosaved", False)
        if start_ts and (now_ts - start_ts) >= 60 and not autosaved:
            _finalize_presence_session()
            st.session_state["presence_autosaved"] = True
    else:
        if was_on:
            _finalize_presence_session()
        st.session_state["presence_autosaved"] = False

    st.session_state["presence_was_on"] = active

    # CSS hook for orb animation duration
    st.markdown(
        """
        <style>
          .presence-orb   {{ animation-duration: {}s; }}
          .presence-phase {{ margin-top:.4rem; }}
        </style>
        """.format(PRESENCE_CYCLE_SEC),
        unsafe_allow_html=True,
    )