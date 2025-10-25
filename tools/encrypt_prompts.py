#!/usr/bin/env python3
"""
Encrypt AGIcyborg prompts (P001–P018) into:
 - manifest.json  (metadata only, no text)
 - prompts.enc    (AES-GCM: iv || ciphertext+tag)

Sources:
  A) Supabase (recommended)
     env: SUPABASE_URL, SUPABASE_SERVICE_ROLE  (service role key)
  B) CSV fallback
     arg: --csv path/to/prompts.csv

Key:
  - Provide base64 128/192/256-bit key via env AGI_KEY_B64
  - If missing, a new 256-bit key is generated and printed ONCE
"""

from __future__ import annotations
import os, json, base64, sys, argparse, secrets
from typing import List, Dict, Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ---- Optional Supabase import (only used if envs provided) ----
try:
    from supabase import create_client
except Exception:
    create_client = None

# ----------------- Key handling -----------------
def get_or_create_key() -> bytes:
    b64 = os.getenv("AGI_KEY_B64", "").strip()
    if b64:
        try:
            key = base64.b64decode(b64)
            if len(key) not in (16, 24, 32):
                raise ValueError("AGI_KEY_B64 must be 128/192/256-bit in base64")
            return key
        except Exception as e:
            print(f"[ERR] Invalid AGI_KEY_B64: {e}", file=sys.stderr)
            sys.exit(1)
    # Generate new 256-bit key
    key = secrets.token_bytes(32)
    print("\n[NEW KEY] Generated a fresh 256-bit key. Store it in your secrets manager:")
    print("AGI_KEY_B64=", base64.b64encode(key).decode("utf-8"), "\n", sep="")
    return key

# ----------------- Data loaders -----------------
def load_from_supabase() -> List[Dict[str, Any]]:
    url  = os.getenv("SUPABASE_URL", "").strip()
    srol = os.getenv("SUPABASE_SERVICE_ROLE", "").strip()  # SERVICE ROLE KEY
    if not url or not srol or create_client is None:
        return []

    sb = create_client(url, srol)

    # pull the 18 canon prompts by source_id P###
    # coalesce prompt_text/prompt to text
    res = (
        sb.table("reflection_prompts")
          .select("id, source_id, theme, frequency_weight, tone_template, active, prompt_text, prompt")
          .eq("active", True)
          .like("source_id", "P%")
          .execute()
    )
    rows = res.data or []
    # normalize records
    out = []
    for r in rows:
        text = r.get("prompt_text") or r.get("prompt") or ""
        out.append({
            "id": r["id"],
            "source_id": r.get("source_id"),
            "theme": r.get("theme"),
            "frequency_weight": r.get("frequency_weight", 1),
            "tone_template": r.get("tone_template") or "Awakened Guide",
            "active": bool(r.get("active", True)),
            "text": str(text).strip(),
        })
    # keep only with text & source_id
    out = [x for x in out if x["text"] and x.get("source_id")]
    # stable sort by numeric part of P###
    def pnum(sid: str) -> int:
        try:
            return int("".join(ch for ch in sid if ch.isdigit()))
        except Exception:
            return 0
    out.sort(key=lambda r: pnum(r["source_id"]))
    return out

def load_from_csv(path: str) -> List[Dict[str, Any]]:
    import csv
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            text = (row.get("prompt_text") or row.get("prompt") or "").strip()
            if not text:
                continue
            out.append({
                "id": row.get("id") or row.get("uuid") or row.get("ID") or "",
                "source_id": row.get("source_id") or row.get("Source ID") or row.get("source"),
                "theme": row.get("theme") or row.get("Theme"),
                "frequency_weight": float(row.get("frequency_weight") or 1),
                "tone_template": row.get("tone_template") or "Awakened Guide",
                "active": str(row.get("active", "true")).strip().lower() in ("1","t","true","yes","y"),
                "text": text,
            })
    # filter to P### if present
    out = [x for x in out if x.get("source_id", "").startswith("P") and x["text"]]
    return out

# ----------------- Encryption -----------------
def encrypt_prompts(records: List[Dict[str, Any]], key: bytes) -> bytes:
    """
    Input: records with 'id' and 'text'.
    Output: binary blob = IV(12 bytes) || AESGCM(ciphertext+tag)
    Payload is JSON: [{"id": ..., "text": ...}, ...]
    """
    payload = [{"id": r["id"], "text": r["text"]} for r in records]
    pt = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    iv = secrets.token_bytes(12)  # AES-GCM standard nonce size
    ct = AESGCM(key).encrypt(iv, pt, None)
    return iv + ct  # single binary blob

# ----------------- Manifest build -----------------
def build_manifest(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    # exclude plaintext; include only metadata used by the runtime
    return {
        "version": 1,
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "items": [
            {
                "id": r["id"],
                "source_id": r["source_id"],
                "theme": r["theme"],
                "frequency_weight": r.get("frequency_weight", 1),
                "tone_template": r.get("tone_template") or "Awakened Guide",
                "active": bool(r.get("active", True)),
            }
            for r in records
        ]
    }

# ----------------- Main -----------------
def main():
    ap = argparse.ArgumentParser(description="Encrypt AGIcyborg prompts → prompts.enc & manifest.json")
    ap.add_argument("--csv", help="CSV file to load prompts (fallback if Supabase not used)", default=None)
    ap.add_argument("--outdir", help="Output dir (default: current)", default=".")
    args = ap.parse_args()

    # 1) Load source
    records = []
    if os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE") and create_client is not None:
        print("[*] Loading prompts from Supabase…")
        records = load_from_supabase()
    elif args.csv:
        print(f"[*] Loading prompts from CSV: {args.csv}")
        records = load_from_csv(args.csv)
    else:
        print("[ERR] No source configured. Set SUPABASE_URL & SUPABASE_SERVICE_ROLE or pass --csv file.", file=sys.stderr)
        sys.exit(2)

    if not records:
        print("[ERR] No prompts loaded (after filtering).", file=sys.stderr)
        sys.exit(3)

    # 2) Build manifest (no plaintext)
    manifest = build_manifest(records)

    # 3) Encrypt texts
    key = get_or_create_key()
    blob = encrypt_prompts(records, key)

    # 4) Write outputs
    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)
    manifest_path = os.path.join(outdir, "manifest.json")
    enc_path = os.path.join(outdir, "prompts.enc")

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    with open(enc_path, "wb") as f:
        f.write(blob)

    print(f"[OK] Wrote {manifest_path} (no plaintext)")
    print(f"[OK] Wrote {enc_path} (AES-GCM, iv||ciphertext+tag)")
    print(f"[INFO] Items: {len(manifest['items'])}")
    # No plaintext written anywhere

if __name__ == "__main__":
    main()