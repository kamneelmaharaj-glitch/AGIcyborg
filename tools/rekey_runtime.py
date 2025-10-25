#!/usr/bin/env python3
"""
Rotate the Fernet key used to encrypt the runtime blob.

Usage examples:

  # 1) Use existing key from env (AGI_KEY_B64), generate a new one, re-encrypt
  python tools/rekey_runtime.py --in tools/runtime.bin.enc --generate-new --write-env

  # 2) Provide both keys explicitly
  python tools/rekey_runtime.py --in tools/runtime.bin.enc \
      --old-key "$AGI_KEY_B64" --new-key "NEW_FERNET_KEY_HERE" --write-env

  # 3) Dry run (no write)
  python tools/rekey_runtime.py --dry-run

Notes:
- Input defaults to tools/runtime.bin.enc
- Output overwrites input (safe .bak created)
- --write-env updates (or adds) AGI_KEY_B64 in .env by default
"""

from __future__ import annotations
import argparse
import base64
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

try:
    from cryptography.fernet import Fernet
except Exception as e:
    print("ERROR: cryptography is required (pip install cryptography)")
    sys.exit(1)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IN = ROOT / "tools" / "runtime.bin.enc"
DEFAULT_ENV_PATH = ROOT / ".env"


def is_valid_fernet_key(k: str) -> bool:
    try:
        # must be 32 url-safe base64-encoded bytes
        Fernet(k.encode("utf-8"))
        return True
    except Exception:
        return False


def backup_file(p: Path) -> Path:
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    bak = p.with_suffix(p.suffix + f".{ts}.bak")
    shutil.copy2(p, bak)
    return bak


def load_bytes(p: Path) -> bytes:
    with open(p, "rb") as f:
        return f.read()


def write_bytes(p: Path, data: bytes) -> None:
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, p)


def update_env_key(env_path: Path, new_key: str) -> None:
    env_path.parent.mkdir(parents=True, exist_ok=True)
    if env_path.exists():
        lines = env_path.read_text().splitlines()
    else:
        lines = []

    out = []
    replaced = False
    for line in lines:
        if line.strip().startswith("AGI_KEY_B64="):
            out.append(f"AGI_KEY_B64={new_key}")
            replaced = True
        else:
            out.append(line)

    if not replaced:
        out.append(f"AGI_KEY_B64={new_key}")

    env_path.write_text("\n".join(out) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Rotate Fernet key for runtime blob")
    ap.add_argument("--in", dest="in_path", default=str(DEFAULT_IN),
                    help=f"Path to encrypted runtime blob (default: {DEFAULT_IN})")
    ap.add_argument("--old-key", dest="old_key", default=os.getenv("AGI_KEY_B64"),
                    help="Existing Fernet key (default: from $AGI_KEY_B64)")
    ap.add_argument("--new-key", dest="new_key", help="New Fernet key to use")
    ap.add_argument("--generate-new", action="store_true",
                    help="Generate a fresh Fernet key (ignored if --new-key provided)")
    ap.add_argument("--write-env", action="store_true",
                    help=f"Write/update AGI_KEY_B64 in {DEFAULT_ENV_PATH}")
    ap.add_argument("--env-path", default=str(DEFAULT_ENV_PATH),
                    help=f"Path to .env to update (default: {DEFAULT_ENV_PATH})")
    ap.add_argument("--dry-run", action="store_true", help="Do not write any files")
    args = ap.parse_args()

    in_path = Path(args.in_path)
    if not in_path.exists():
        print(f"ERROR: Input not found: {in_path}")
        sys.exit(2)

    old_key = args.old_key
    if not old_key:
        print("ERROR: --old-key not provided and $AGI_KEY_B64 not set")
        sys.exit(2)
    if not is_valid_fernet_key(old_key):
        print("ERROR: old key is not a valid Fernet key")
        sys.exit(2)

    if args.new_key:
        new_key = args.new_key
    elif args.generate_new:
        new_key = Fernet.generate_key().decode()
    else:
        print("ERROR: provide --new-key or --generate-new")
        sys.exit(2)

    if not is_valid_fernet_key(new_key):
        print("ERROR: new key is not a valid Fernet key")
        sys.exit(2)

    print(f"🔑 Old key:  {old_key[:6]}… (hidden)")
    print(f"🆕 New key:  {new_key[:6]}… (hidden)")
    print(f"📦 Blob in:  {in_path}")

    # Read & decrypt with old key
    blob = load_bytes(in_path)
    try:
        plain = Fernet(old_key.encode()).decrypt(blob)
    except Exception as e:
        print(f"❌ Decrypt with old key failed: {e}")
        sys.exit(3)

    print(f"✅ Decrypted OK (len={len(plain)} bytes)")

    # Re-encrypt with new key
    new_blob = Fernet(new_key.encode()).encrypt(plain)

    if args.dry_run:
        print("🔎 Dry run: not writing output")
        print(f"Would write {len(new_blob)} bytes to {in_path} (backup created)")
        print(f"Export new key for testing:\n\n  export AGI_KEY_B64='{new_key}'\n")
        sys.exit(0)

    # Backup and write
    bak = backup_file(in_path)
    write_bytes(in_path, new_blob)
    print(f"💾 Wrote new blob -> {in_path}")
    print(f"🧷 Backup saved -> {bak}")

    # Optionally update .env
    if args.write_env:
        env_path = Path(args.env_path)
        update_env_key(env_path, new_key)
        print(f"📝 Updated {env_path} with AGI_KEY_B64")

    # Show export line for immediate use
    print("\nNext steps:")
    print(f"  export AGI_KEY_B64='{new_key}'")
    print("  python -m tools.test_runtime_call   # should still succeed\n")


if __name__ == "__main__":
    main()