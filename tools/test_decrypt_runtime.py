# tools/test_decrypt_runtime.py
import os, sys, pathlib
from cryptography.fernet import Fernet, InvalidToken

def main():
    key_b64 = os.environ.get("AGI_KEY_B64")
    print(f"🔑 AGI_KEY_B64: {key_b64!r}")
    if not key_b64:
        print("❌ Environment variable AGI_KEY_B64 not set")
        sys.exit(1)

    enc_path = pathlib.Path("tools/payload.bin.enc")
    if not enc_path.exists():
        print(f"❌ Encrypted file not found: {enc_path.resolve()}")
        sys.exit(1)

    try:
        f = Fernet(key_b64.encode())
        ciphertext = enc_path.read_bytes()
        print(f"📦 Ciphertext length: {len(ciphertext)} bytes")
        plaintext = f.decrypt(ciphertext)
        print("✅ Decrypted OK:")
        print(plaintext.decode(errors="ignore"))
    except InvalidToken:
        print("❌ InvalidToken: The key doesn’t match the encrypted file.")
    except Exception as e:
        print(f"❌ Exception: {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()