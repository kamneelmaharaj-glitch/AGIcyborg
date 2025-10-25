from tools.inmem_loader import load_runtime
# tools/test_runtime_call.py  (top of file)
import sys

try:
    from tools.validate_env import validate_env
except Exception:
    validate_env = None  # keep backward compatible

if validate_env is not None:
    rc = validate_env(".env")
    if rc != 0:
        sys.exit(1)
rt = load_runtime("tools/runtime.bin.enc")
print(rt.generate_insight("Clarity", "I'm learning to see things as they are."))