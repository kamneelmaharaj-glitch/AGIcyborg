#!/usr/bin/env bash
set -Eeuo pipefail
set -x

cd "$(dirname "$0")"

# venv
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
# --- Validate env before running anything that depends on it ---
if python -c "import tools.validate_env as v; exit(v.validate_env('.env'))"; then
  echo "✅ .env validated"
else
  echo "❌ .env invalid. Fix the issues above and rerun." >&2
  exit 1
fi

# dotenv for auto .env loading
python - <<'PY'
import importlib.util, sys
print("dotenv installed:", importlib.util.find_spec("dotenv") is not None)
PY

pip install -U pip wheel >/dev/null
pip install python-dotenv >/dev/null || true

# load .env for this shell too (helpful if code doesn’t auto-load)
if [[ -f .env ]]; then
  set -a; source .env; set +a
fi

# smoke test: runtime + license
python - <<'PY'
from tools.inmem_loader import verify_license_or_raise, load_runtime
from pathlib import Path
verify_license_or_raise(None)
rt = load_runtime(Path("tools/runtime.bin.enc"))
print(rt.generate_insight("Clarity", "check"))
PY
