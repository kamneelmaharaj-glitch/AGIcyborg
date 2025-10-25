# tools/inmem_loader.py
from __future__ import annotations

import os
import re
import json
import time
import base64
import hashlib
import platform
from pathlib import Path
from types import ModuleType
from importlib import util as importlib_util

# Auto-load .env keys for local dev
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except Exception:
    pass

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class RuntimeAuthError(Exception):
    """Raised when license / key material is invalid."""
    pass


# ---------------------------------------------------------------------------
# Base64 helpers
# ---------------------------------------------------------------------------
def b64u(data: bytes) -> str:
    """base64url encode without '=' padding."""
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def b64u_decode(s: str) -> bytes:
    """base64url decode accepting unpadded input."""
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _urlsafe_b64decode_clean(s: str) -> bytes:
    """
    Decode a urlsafe base64 string after cleaning and fixing padding.
    Accepts only [A-Za-z0-9_-]; strips everything else; adds '=' padding.
    """
    if not isinstance(s, str):
        raise RuntimeAuthError("AGI_PUBKEY_B64 must be a string")
    s = s.strip()
    s = re.sub(r"[^A-Za-z0-9_-]", "", s)
    s += "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s)


# ---------------------------------------------------------------------------
# Public key loading (no import-time decode)
# ---------------------------------------------------------------------------
def _load_pubkey_b64() -> str:
    """
    Read urlsafe base64 public key (Ed25519) from file first, then env fallback.
    File path: tools/keys/agi_ed25519_public.key
    Env var : AGI_PUBKEY_B64
    """
    file_path = ROOT / "tools" / "keys" / "agi_ed25519_public.key"
    if file_path.exists():
        return file_path.read_text(encoding="ascii", errors="ignore").strip()

    env_b64 = (os.getenv("AGI_PUBKEY_B64") or "").strip()
    if env_b64:
        return env_b64

    raise RuntimeAuthError(
        "No AGI_PUBKEY_B64 found (set env or create tools/keys/agi_ed25519_public.key)."
    )


def load_pubkey_bytes() -> bytes:
    """
    Return raw 32-byte Ed25519 public key (decoded at call time, not import).
    """
    b64 = _load_pubkey_b64()
    try:
        raw = _urlsafe_b64decode_clean(b64)
    except Exception as e:
        raise RuntimeAuthError(f"Invalid AGI_PUBKEY_B64 (base64 decode): {e}")

    if len(raw) != 32:
        raise RuntimeAuthError(
            f"AGI_PUBKEY_B64 decoded to {len(raw)} bytes (expected 32 for Ed25519)."
        )
    return raw


# ---------------------------------------------------------------------------
# Machine fingerprint (optional binding)
# ---------------------------------------------------------------------------
def get_machine_fingerprint() -> str:
    """
    A lightweight HW fingerprint: platform tuple + primary MAC.
    """
    import uuid
    plat = "|".join(platform.uname())
    mac = str(uuid.getnode())
    raw = (plat + "|" + mac).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


# ---------------------------------------------------------------------------
# License verification (Ed25519)
# ---------------------------------------------------------------------------
def verify_license_or_raise(lic_b64: str | None = None) -> dict:
    """
    Verify a signed license token.
    - Reads token from lic_b64 (env: AGI_LIC_B64) or tools/license.jwt
    - Verifies signature against Ed25519 pubkey (from file/env)
    - Checks exp >= now, optional machine binding
    Returns the decoded payload dict if valid.
    """
    # 1) load token
    if not lic_b64:
        lic_file = ROOT / "tools" / "license.jwt"
        if lic_file.exists():
            lic_b64 = lic_file.read_text().strip()
    if not lic_b64:
        raise RuntimeAuthError("No license provided (set $AGI_LIC_B64 or tools/license.jwt).")

    # 2) parse token: header.payload.signature (each base64url)
    try:
        parts = lic_b64.strip().split(".")
        if len(parts) != 3:
            raise ValueError("token must be header.payload.signature")
        h_b64, p_b64, s_b64 = parts
        header = json.loads(b64u_decode(h_b64))
        payload = json.loads(b64u_decode(p_b64))
        sig = b64u_decode(s_b64)
    except Exception as e:
        raise RuntimeAuthError(f"Invalid license format: {e}")

    # 3) verify signature using runtime-loaded pubkey
    pub_raw = load_pubkey_bytes()
    pub = Ed25519PublicKey.from_public_bytes(pub_raw)
    signed_data = f"{h_b64}.{p_b64}".encode("utf-8")
    try:
        pub.verify(sig, signed_data)
    except InvalidSignature:
        raise RuntimeAuthError("License signature invalid.")

    # 4) check expiry
    now = int(time.time())
    if "exp" not in payload or not isinstance(payload["exp"], int):
        raise RuntimeAuthError("License missing 'exp' (unix timestamp).")
    if payload["exp"] < now:
        raise RuntimeAuthError("License expired.")

    # 5) optional machine binding
    expected_hw = payload.get("hw")
    if expected_hw:
        local_hw = get_machine_fingerprint()
        if local_hw != expected_hw:
            raise RuntimeAuthError("License not valid for this machine (hw mismatch).")

    return payload


# ---------------------------------------------------------------------------
# In-memory dynamic import (post-decrypt)
# ---------------------------------------------------------------------------
def _compile_module_from_bytes(source: bytes, module_name: str) -> ModuleType:
    spec = importlib_util.spec_from_loader(module_name, loader=None)
    module = importlib_util.module_from_spec(spec)
    code = compile(source, module_name, "exec")
    exec(code, module.__dict__)
    return module


def load_runtime(enc_path: str | os.PathLike[str]) -> ModuleType:
    """
    Loads an encrypted python module into memory after:
      1) License verification
      2) Fernet decrypt (key from $AGI_KEY_B64)
    No plaintext is persisted to disk.
    """
    # --- License check (fails fast) ---
    lic_env = os.getenv("AGI_LIC_B64")
    verify_license_or_raise(lic_env)  # raises if invalid

    # --- Key + decrypt ---
    key_b64 = os.getenv("AGI_KEY_B64")
    if not key_b64:
        raise RuntimeAuthError("AGI_KEY_B64 not set")
    try:
        f = Fernet(key_b64.encode("utf-8"))
    except Exception:
        raise RuntimeAuthError("AGI_KEY_B64 is not a valid Fernet key")

    raw = Path(enc_path).read_bytes()
    try:
        plain = f.decrypt(raw)
    except Exception as e:
        raise RuntimeAuthError(f"Decryption failed: {e}")

    # --- Dyn-import ---
    mod = _compile_module_from_bytes(plain, module_name="agimirror_runtime")
    return mod