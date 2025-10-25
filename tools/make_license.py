# tools/make_license.py
# Create a signed license token for local testing.
# Usage:
#   AGI_LICENSE_SECRET=your-32-64byte-secret \
#   python tools/make_license.py --owner "Kamneel" --license-id "AGI-2025-001" --days 365 --bind-host

from __future__ import annotations
import os
import json
import hmac
import base64
import hashlib
import argparse
from datetime import datetime, timedelta, timezone
import socket

def b64url(d: bytes) -> str:
    return base64.urlsafe_b64encode(d).rstrip(b"=").decode("ascii")

def sign(payload_bytes: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    return b64url(mac)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", required=True)
    ap.add_argument("--license-id", required=True)
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--bind-host", action="store_true")
    args = ap.parse_args()

    secret = os.getenv("AGI_LICENSE_SECRET", "")
    if not secret:
        raise SystemExit("AGI_LICENSE_SECRET is required")

    now = datetime.now(timezone.utc)
    payload = {
        "license_id": args.license_id,
        "owner": args.owner,
        "issued_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expiry": (now + timedelta(days=args.days)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if args.bind_host:
        payload["host"] = socket.gethostname().lower()

    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    token = f"{b64url(payload_bytes)}.{sign(payload_bytes, secret)}"
    print(token)

if __name__ == "__main__":
    main()