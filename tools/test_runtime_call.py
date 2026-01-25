# tools/test_runtime_call.py
from __future__ import annotations

import sys

from tools.inmem_loader import load_runtime, RuntimeAuthError

try:
    from tools.validate_env import validate_env
except Exception:
    validate_env = None  # keep backward compatible

if validate_env is not None:
    rc = validate_env(".env")
    if rc != 0:
        print("⚠️  No .env found. Continuing anyway (runtime call test).")

try:
    rt = load_runtime("tools/runtime.bin.enc")
except RuntimeAuthError as e:
    print(f"⚠️  Skipping runtime call test (license missing/invalid): {e}")
    sys.exit(0)

print(rt.generate_insight("Clarity", "I'm learning to see things as they are."))