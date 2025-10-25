# tools/gen_keys.py
from __future__ import annotations
import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

priv = Ed25519PrivateKey.generate()
pub  = priv.public_key()

priv_b64 = base64.b64encode(priv.private_bytes(
    encoding = __import__("cryptography.hazmat.primitives.serialization", fromlist=[""]).Encoding.Raw,
    format   = __import__("cryptography.hazmat.primitives.serialization", fromlist=[""]).PrivateFormat.Raw,
    encryption_algorithm = __import__("cryptography.hazmat.primitives.serialization", fromlist=[""]).NoEncryption()
)).decode()

pub_b64  = base64.b64encode(pub.public_bytes(
    encoding = __import__("cryptography.hazmat.primitives.serialization", fromlist=[""]).Encoding.Raw,
    format   = __import__("cryptography.hazmat.primitives.serialization", fromlist=[""]).PublicFormat.Raw
)).decode()

print("KEEP PRIVATE (do not commit):")
print(f"AGI_PRIVKEY_B64={priv_b64}\n")
print("Embed or set on server:")
print(f"AGI_PUBKEY_B64={pub_b64}")