# AGIcyborg — Architecture

> High-level view of the runtime, data flow, trust boundaries, and deployment.  
> All diagrams use GitHub-compatible Mermaid.

---
```mermaid
flowchart TD
  %% ---------------------------
  %%  System Overview Diagram
  %% ---------------------------

  %% Nodes
  U[User / Browser]
  S[Streamlit UI]
  DB[(Supabase Postgres)]
  OA[OpenAI Mentor]
  RT[Encrypted Runtime]
  LIC[[License JWT]]
  PK[[AGI_PUBKEY_B64]]
  KEY[[AGI_KEY_B64]]
  BIN[(runtime.bin.enc)]
  PR[(reflection_prompts)]
  MI[(mentor_insights)]
  UR[(user_reflections)]

  %% 1) App flows
  U --> S
  S -->|Fetch Save| DB
  S -->|Optional guidance| OA
  S -->|Load decrypt in memory| RT

  %% 2) Runtime load and verification
  RT -->|validate| LIC
  LIC -->|ed25519 verify with| PK
  RT -->|decrypt using| KEY
  RT -->|reads| BIN

  %% 3) Data groupings (tables inside DB)
  DB --- PR
  DB --- MI
  DB --- UR

  ```mermaid
  %% ---------------------------
  %%  Trust Boundary Diagram
  %% ---------------------------

  subgraph BROWSER[Browser / User Device]
    U[User]
  end

  subgraph HOST[App Host]
    S[Streamlit App]
    L[Loader]
    R[Runtime (in-memory)]
  end

  subgraph SECRETS[Host Secrets]
    PK[AGI_PUBKEY_B64]
    K[AGI_KEY_B64]
    LIC[AGI_LIC_B64]
  end

  subgraph CLOUD[Supabase Cloud]
    DB[(Postgres)]
  end

  subgraph OPENAI[OpenAI Cloud]
    OA[OpenAI API]
  end

  %% Connections
  U --> S
  S --> DB
  S --> OA
  S --- L
  L --> R
  S -.reads.-> SECRETS

  %% Styling
  classDef boundary stroke-dasharray: 4 4;
  class BROWSER,HOST,SECRETS,CLOUD,OPENAI boundary;

  flowchart TD
  ```mermaid
  %% ---------------------------
  %%  Deployment Topology Diagram
  %% ---------------------------

  DEV[Dev Laptop] --> GH[GitHub Repo]
  GH -->|pull/clone| HOST[App Host]
  HOST -->|env vars| SECRETS[AGI_PUBKEY_B64 / AGI_KEY_B64 / AGI_LIC_B64]
  HOST --> DB[(Supabase Postgres)]
  HOST --> OA[OpenAI API]
  U[User] --> HOST

  %% Styling
  classDef infra fill:#f1f8ff,stroke:#7fb3ff,color:#003b73;
  classDef ext fill:#fff9e6,stroke:#ffc056,color:#6c3b00;

  class HOST,DB infra;
  class OA ext;

  erDiagram
  ```mermaid
  %% ---------------------------
  %%  Data Model ER Diagram
  %% ---------------------------

  reflection_prompts {
    uuid id
    string theme
    string prompt
    numeric frequency_weight
    bool active
  }

  mentor_insights {
    uuid id
    string theme
    string insight
    string mantra
  }

  user_reflections {
    uuid id
    uuid prompt_id
    string theme
    text reflection_text
    text generated_insight
    text generated_mantra
    timestamp created_at
  }

  reflection_prompts ||--o{ user_reflections : "via prompt_id"
  mentor_insights   ||--o{ user_reflections : "inspired insight"

  sequenceDiagram
  autonumber
  participant U as User
  participant S as Streamlit App
  participant L as Loader
  participant ENV as Env Secrets
  participant LIC as License JWT (AGI_LIC_B64)
  participant PK as Public Key (AGI_PUBKEY_B64)
  participant BIN as Encrypted Blob (runtime.bin.enc)
  participant RT as Runtime (in-memory)

  U->>S: Request action that needs runtime
  S->>L: load_runtime()
```mermaid
  %% --- License verification ---
  L->>ENV: Read LIC & PK
  L->>L: Decode LIC (header.payload.sig)
  L->>L: Verify Ed25519(sig, header.payload, PK)

  alt Invalid license
    L-->>S: Abort (RuntimeAuthError: invalid license)
    S-->>U: Error surfaced to UI
  else Valid license
    %% --- Decrypt & import in memory ---
    L->>BIN: Read encrypted bytes (ciphertext)
    L->>ENV: Read KEY (AGI_KEY_B64)
    L->>L: Fernet(KEY).decrypt(ciphertext)
    L->>RT: Import module from bytes (no disk write)
    S->>RT: Call guarded API
    RT-->>S: Result
    S-->>U: Response
  end

  Threats & Mitigations

Scope: runtime loading, license validation, key handling, and boundary crossings.

#
Threat
Likely Vector(s)
Primary Mitigations (built-in)
Residual Risk / What to Watch
Runbook / Actionables
T1
Leaked Fernet key (AGI_KEY_B64)
Misconfigured env, logs, support tickets, CI artifacts
Key never printed; least-priv env on host; .env validator; no plaintext runtime on disk
Host compromise still exposes env at rest
Rotate: generate new Fernet key, re-encrypt runtime.bin.enc, update host secret; invalidate old key in secrets store
T2
Leaked License JWT (AGI_LIC_B64)
Screenshots, logs, cache, chat pastes
JWT validated against pubkey; short exp; hardware binding optional
Replay on same host until exp; detection relies on logs
Re-issue license with shorter TTL; enable HW bind (host fingerprint) for sensitive tenants
T3
Tampered License
Modified header/payload/signature
Ed25519 verify with AGI_PUBKEY_B64 before decryption
None if pubkey is intact
Keep pubkey in read-only secrets; verify at startup and on each load
T4
Modified runtime blob
Replacing runtime.bin.enc
Decryption fails under wrong key/IV/MAC
Malicious but valid blob encrypted with same key (unlikely without key)
Sign the plaintext at build and verify signature after decrypt, before import
T5
Memory scraping
Root on host; ptrace; crash dumps
In-memory decrypt only; no plaintext on disk
Root can still read memory
Run on hardened host; disable core dumps; ptrace_scope/equivalent; minimal process privileges
T6
Secrets in logs
Verbose logging; exception dumps
No logging of env in loader; .env validator rejects risky patterns
3rd-party libs may log unexpectedly
Set log level to INFO; scrubgers in log pipeline; CI rule: fail on secrets regex
T7
OpenAI misuse / overage
Stolen API key; unbounded calls
Rate-limit; role-based environment; separate key per env
Key still exfiltrable if host compromised
Put key in per-service vault; IP restrict; alerts on anomaly (spend, rps)
T8
Supabase exfiltration
Leaked DB URL/key; SQL injection
Parametrized queries; least-priv service key; no raw admin key on host
Privilege escalation via lateral movement
Restrict RLS policies; rotate service key; alert on unusual query volume
T9
Rollback / stale runtime
Old encrypted blob deployed
Startup check compares build id/version in decrypted module
If attacker gets old blob + valid key
Enforce monotonic version in license; deny if runtime.version < min_version
T10
Supply chain (pip)
Malicious dependencies
Hash-pin deps; lockfile in repo; pip install --require-hashes
New CVEs between rotations
Weekly dep audit; pip-audit in CI; renovate bot with human review


⸻

Operational Playbook (quick copy)
	•	Rotate Fernet key
	1.	Generate: python - <<'PY'\nfrom cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\nPY
	2.	Re-encrypt: python tools/encrypt_blob.py tools/runtime.bin > tools/runtime.bin.enc
	3.	Update secret AGI_KEY_B64 on host; restart app.
	4.	Verify: loader decrypts & imports; smoke test passes.
	•	Re-issue License
	1.	Create short-lived JWT (e.g., 7–30 days) signed with offline Ed25519 private key.
	2.	(Optional) Add hw claim (host fingerprint) and min_runtime_version.
	3.	Update AGI_LIC_B64 on host; reload; check logs for “License OK”.
	•	Harden host
	•	Disable core dumps (ulimit -c 0), lock down ptrace (kernel.yama.ptrace_scope=1 or OS equivalent).
	•	Run app as non-root; minimal file perms on .env and tools/.
	•	Separate build box (creates runtime.bin.enc) from run box (never sees plaintext runtime).
	•	Monitoring
	•	Alerts on: license verification failures, decrypt failures, version rollback attempts, abnormal OpenAI spend, high DB query rate.
	•	Keep redacted security logs for forensics (no secrets).
