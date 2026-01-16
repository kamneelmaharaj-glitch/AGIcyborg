# tests/manual/test_openai.py
from __future__ import annotations

import os


def _has_real_openai_key() -> bool:
    k = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not k:
        return False
    # Treat obvious placeholders as "not real"
    if k.lower() in {"changeme", "your_key_here", "none", "null"}:
        return False
    if "sk-proj" in k and "..." in k:
        return False
    return True


def test_openai_manual_smoke() -> None:
    import pytest

    if not _has_real_openai_key():
        pytest.skip("Manual test: set OPENAI_API_KEY to a real key to run.")

    from openai import OpenAI

    client = OpenAI()
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say 'ok'."}],
    )
    assert resp.choices[0].message.content


if __name__ == "__main__":
    if not _has_real_openai_key():
        print("[SKIP] Set OPENAI_API_KEY to run this manual test.")
        raise SystemExit(0)

    from openai import OpenAI

    client = OpenAI()
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say 'ok'."}],
    )
    print(resp.choices[0].message.content)
