# tools/encrypt_blob.py
import os, sys, pathlib
from cryptography.fernet import Fernet

def main():
    if len(sys.argv) != 2:
        print("Usage: python tools/encrypt_blob.py <path-to-input-file>")
        sys.exit(1)

    key_b64 = os.environ.get("AGI_KEY_B64")
    if not key_b64:
        print("❌ AGI_KEY_B64 not set.")
        sys.exit(1)

    src = pathlib.Path(sys.argv[1]).expanduser().resolve()
    if not src.exists():
        print(f"❌ Input not found: {src}")
        sys.exit(1)

    dst = src.with_suffix(src.suffix + ".enc")
    f = Fernet(key_b64.encode())
    data = src.read_bytes()
    dst.write_bytes(f.encrypt(data))
    print(f"✅ Encrypted: {src.name} → {dst.name}")

if __name__ == "__main__":
    main()