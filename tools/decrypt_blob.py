# tools/decrypt_blob.py
import os, sys, pathlib
from cryptography.fernet import Fernet, InvalidToken

def main():
    if len(sys.argv) != 3:
        print("Usage: python tools/decrypt_blob.py <input.enc> <output>")
        sys.exit(1)

    key_b64 = os.environ.get("AGI_KEY_B64")
    if not key_b64:
        print("❌ AGI_KEY_B64 not set.")
        sys.exit(1)

    enc_path = pathlib.Path(sys.argv[1]).resolve()
    out_path = pathlib.Path(sys.argv[2]).resolve()

    if not enc_path.exists():
        print(f"❌ Encrypted file not found: {enc_path}")
        sys.exit(1)

    try:
        f = Fernet(key_b64.encode())
        out_path.write_bytes(f.decrypt(enc_path.read_bytes()))
        print(f"✅ Decrypted → {out_path}")
    except InvalidToken:
        print("❌ InvalidToken: wrong key or corrupted file.")
        sys.exit(2)

if __name__ == "__main__":
    main()