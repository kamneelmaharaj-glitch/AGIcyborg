# tools/dev_sign_license.py
from __future__ import annotations
import json, time, re, base64
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]

def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

def b64u_decode_clean(s: str) -> bytes:
    s = re.sub(r"[^A-Za-z0-9_-]", "", s.strip())
    s += "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s)

priv_path = ROOT / "tools" / "keys" / "agi_ed25519_private.key"
priv_b64  = priv_path.read_text(encoding="ascii", errors="ignore").strip()
priv_raw  = b64u_decode_clean(priv_b64)

# Accept 32-byte seed or 64-byte (seed+pub) forms
if len(priv_raw) == 64:
    priv_raw = priv_raw[:32]
elif len(priv_raw) != 32:
    raise SystemExit(f"Private key must be 32 or 64 bytes raw; got {len(priv_raw)}")

priv = Ed25519PrivateKey.from_private_bytes(priv_raw)

# Build a license payload (edit as you wish)
now = int(time.time())
payload = {
    "sub": "Kamneel Maharaj",
    "scope": "runtime:access",
    "exp": now + 30*86400,       # valid 30 days
    "issued": now,
    "version": "alpha-1",
    # optional machine binding:
    # "hw": "machine_fingerprint_here",
}

header  = {"alg": "EdDSA", "typ": "JWT"}
h_b64   = b64u(json.dumps(header, separators=(",", ":")).encode())
p_b64   = b64u(json.dumps(payload, separators=(",", ":")).encode())
to_sign = f"{h_b64}.{p_b64}".encode()

sig     = priv.sign(to_sign)
s_b64   = b64u(sig)
token   = f"{h_b64}.{p_b64}.{s_b64}"

out = ROOT / "tools" / "license.jwt"
out.write_text(token)
print("✅ Wrote license to", out)
print(token)