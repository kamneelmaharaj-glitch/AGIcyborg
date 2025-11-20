# agi/auth.py
from __future__ import annotations
import uuid
import streamlit as st
from typing import Optional
from .db import upsert_profile

S_USER_EMAIL = "user_email"
S_USER_ID = "user_id"

def _derive_user_id(email: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, email.strip().lower())

def sign_out():
    for k in [S_USER_EMAIL, S_USER_ID, "auth_email_input", "auth_display_input"]:
        st.session_state.pop(k, None)

def auth_gate(sb) -> Optional[str]:
    # Optional: dev bypass
    dev_email = st.secrets.get("DEV_BYPASS_EMAIL")
    if dev_email and S_USER_ID not in st.session_state:
        uid = _derive_user_id(dev_email)
        st.session_state[S_USER_EMAIL] = dev_email
        st.session_state[S_USER_ID] = str(uid)
        try: upsert_profile(sb, uid, dev_email, "Dev")
        except Exception: pass
        return str(uid)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 👤 Account")
    uid = st.session_state.get(S_USER_ID)
    email = st.session_state.get(S_USER_EMAIL)

    if uid and email:
        st.sidebar.write(f"Signed in as **{email}**")
        if st.sidebar.button("Sign out"):
            sign_out()
            st.rerun()
        return uid

    st.sidebar.write("Enter your email to personalize your space:")
    email_in = st.sidebar.text_input("Email", key="auth_email_input", placeholder="you@example.com")
    display   = st.sidebar.text_input("Display name (optional)", key="auth_display_input", placeholder="e.g., Kam")
    if st.sidebar.button("Continue"):
        email_in = (email_in or "").strip()
        if "@" not in email_in:
            st.sidebar.error("Please enter a valid email.")
            return None
        uid = _derive_user_id(email_in)
        st.session_state[S_USER_EMAIL] = email_in
        st.session_state[S_USER_ID] = str(uid)
        try: upsert_profile(sb, uid, email_in, (display or None))
        except Exception: pass
        st.rerun()
    return None