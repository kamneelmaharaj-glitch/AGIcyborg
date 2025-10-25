#!/usr/bin/env python3
"""
AGIcyborg Environment Validator
-------------------------------
Checks your `.env` for:
 - Missing required keys
 - Truncated or malformed keys (like RL=, EY=, B64=)
 - Invalid Base64 formats
"""

import re
import base64
from pathlib import Path

REQUIRED_KEYS = [
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "OPENAI_API_KEY",
    "AGI_KEY_B64",
    "AGI_PUBKEY_B64",
]

B64_RE = re.compile(r"^[A-Za-z0-9_-]{32,}={0,2}$")

def validate_env(env_path=".env"):
    env_file = Path(env_path)
    if not env_file.exists():
        print(f"❌ No {env_path} found.")
        return 1

    text = env_file.read_text(encoding="utf-8").replace("\r", "")
    lines = text.splitlines()

    found = {}
    issues = []

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            issues.append(f"⚠️ Line {i}: Missing '=' — {line}")
            continue

        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()

        found[k] = v

        # Common truncation patterns
        if k in {"RL", "EY", "B64"}:
            issues.append(f"⚠️ Line {i}: Key '{k}' looks truncated — expected SUPABASE_URL, SUPABASE_KEY, or AGI_PUBKEY_B64.")
        elif not k:
            issues.append(f"⚠️ Line {i}: Empty key name.")

        # Base64 sanity checks
        if "B64" in k:
            try:
                b = base64.urlsafe_b64decode(v + "=" * ((4 - len(v) % 4) % 4))
                if not (16 <= len(b) <= 128):
                    issues.append(f"⚠️ {k}: Decoded length {len(b)} looks unusual.")
            except Exception:
                issues.append(f"⚠️ {k}: Invalid Base64 encoding.")

    # Check missing required keys
    for req in REQUIRED_KEYS:
        if req not in found:
            issues.append(f"❌ Missing {req}")

    # Summary
    if issues:
        print("\n".join(issues))
        print("\n🔎 Validation completed with warnings/errors.")
        return 1
    else:
        print("✅ All required environment keys are present and look valid.")
        return 0


if __name__ == "__main__":
    exit(validate_env())