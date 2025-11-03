#!/usr/bin/env bash
# Dev bootstrap for AGIcyborg
# - Creates/activates venv
# - Installs deps
# - Loads .env into the shell
# - Verifies license + decrypts runtime (smoke test)

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

info()  { printf "\033[1;36m› %s\033[0m\n" "$*"; }
ok()    { printf "\033[1;32m✔ %s\033[0m\n" "$*"; }
warn()  { printf "\033[1;33m⚠ %s\033[0m\n" "$*"; }
fail()  { printf "\033[1;31m✘ %s\033[0m\n" "$*"; exit 1; }

python_bin="${PYTHON_BIN:-python3}"

# ---- 1) Python check ---------------------------------------------------------
if ! command -v "$python_bin" >/dev/null 2>&1; then
  fail "python3 not found. Install Xcode CLT and Python 3 (e.g., via homebrew)."
fi
PYVER=$($python_bin - <<'PY' 2>/dev/null || true
import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)
info "Python ${PYVER:-unknown} detected"

# ---- 2) Virtualenv -----------------------------------------------------------
if [[ ! -d ".venv" ]]; then
  info "Creating virtualenv at .venv"
  "$python_bin" -m venv .venv || fail "Failed to create venv"
else
  info "Using existing .venv"
fi

# shellcheck disable=SC1091
source ".venv/bin/activate"
ok "Virtualenv activated"

# ---- 3) Dependencies ---------------------------------------------------------
info "Upgrading pip & wheel"
python -m pip install --upgrade pip wheel >/dev/null

if [[ -f "requirements.txt" ]]; then
  info "Installing requirements.txt"
  pip install -r requirements.txt || fail "pip install failed"
else
  warn "requirements.txt not found (skipping)"
fi

# ---- 4) Load .env into this shell -------------------------------------------
if [[ -f ".env" ]]; then
  info "Loading .env into environment"
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
else
  warn ".env not found; make sure AGI_* variables are exported elsewhere"
fi

# ---- 5) Quick sanity & smoke test -------------------------------------------
info "Running runtime + license verification"
python - <<'PY' || exit $?
import os, json, sys
from pathlib import Path
from tools.inmem_loader import verify_license_or_raise, load_runtime

root = Path(__file__).resolve().parent
errors=[]

# Required secrets
for k in ("AGI_KEY_B64","AGI_PUBKEY_B64"):
    if not os.getenv(k):
        errors.append(f"Missing {k} (set in .env)")

if not (root/"tools/license.jwt").exists() and not os.getenv("AGI_LIC_B64"):
    errors.append("No license provided (tools/license.jwt or $AGI_LIC_B64)")

if errors:
    for e in errors: print("•", e)
    sys.exit(2)

# Verify and decrypt
verify_license_or_raise(os.getenv("AGI_LIC_B64"))
rt = load_runtime(root/"tools/runtime.bin.enc")
out = rt.generate_insight("Clarity", "setup check")
print(json.dumps(out, indent=2))
PY

ok "Dev environment ready"
echo
echo "Next time:  source .venv/bin/activate"
echo