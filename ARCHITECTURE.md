# 🏗️ Architecture — AGIcyborg

## High-Level
- **Streamlit UI**: minimal local interface for reflection and testing.
- **Supabase**: managed Postgres for prompts, insights, and reflection logs.
- **Encrypted Runtime** (`tools/runtime.bin.enc`): core guidance logic, decrypted in-memory only.
- **In-Memory Loader** (`tools/inmem_loader.py`): verifies license, decrypts runtime, dyn-imports.
- **OpenAI (optional)**: AI Mentor layer to personalize insights.
- **Health Page** (`0_Health_Check.py`): status, counts, simple charts, cache refresh.

```
[User] ⇄ Streamlit ── Supabase
                 └─(optional)→ OpenAI
                 └─ inmem_loader → runtime.bin.enc (license+decrypt in-memory)
```

## Data
- `reflection_prompts(id, theme, prompt, frequency_weight, active)`
- `mentor_insights(id, theme, insight, mantra)`
- `user_reflections(prompt_id, theme, reflection_text, generated_insight, generated_mantra, created_at)`

## Security Design
- No plaintext keys or runtime on disk.
- Ed25519-signed license; Fernet decrypt with `AGI_KEY_B64` (from `.env`).
- `.gitignore` excludes `.env`, keys, license, venv, runtime binary.
- Validator `tools/validate_env.py` runs pre-commit and in test harness.
