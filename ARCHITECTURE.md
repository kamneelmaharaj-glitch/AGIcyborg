# AGIcyborg — Architecture

> High-level view of the runtime, data flow, trust boundaries, and deployment.
> All diagrams use GitHub-compatible Mermaid.

---

%% 1) System Overview

```mermaid
flowchart TD
  U[User / Browser] --> S[Streamlit UI]
  S --> DB[(Supabase Postgres)]
  S --> OA[OpenAI API]
  S --> RT[Encrypted Runtime]
  S --> LIC[License Token]
  S --> KEY[Runtime Key - Fernet]

  %% runtime load path
  RT -. binary .-> BIN[runtime.bin.enc]

  %% license verification
  LIC -->|ed25519 verify with pubkey| PK[AGI_PUBKEY_B64]

  %% decrypt
  KEY -->|decrypt| RT

  %% data tables
  DB --- RP[(reflection_prompts)]
  DB --- MI[(mentor_insights)]
  DB --- UR[(user_reflections)]

  classDef store fill:#eef5ff,stroke:#6aa5ff,color:#1a3c6e;
  classDef crypto fill:#fff4e6,stroke:#ffa458,color:#7a3b00;
  classDef runtime fill:#f2f7f2,stroke:#79b57b,color:#0f3d13;

  class DB,RP,MI,UR store
  class LIC,KEY,PK crypto
  class RT,BIN runtime

%% 2) Runtime Load & Verify (Sequence)

  sequenceDiagram
  autonumber
  participant UI as Streamlit App
  participant L  as Loader
  participant V  as Verifier
  participant C  as Crypto
  participant R  as Runtime (in-memory)

  UI->>L: request runtime
  L->>V: validate license (AGI_LIC_B64)
  V->>V: ed25519 verify with AGI_PUBKEY_B64
  V-->>L: ok / fail

  alt license ok
    L->>C: read runtime.bin.enc
    L->>C: get Fernet key (AGI_KEY_B64)
    C->>C: decrypt bytes
    C-->>L: plaintext module bytes
    L->>R: compile & exec in-memory
    R-->>UI: module loaded
  else invalid license
    L-->>UI: error (invalid license)
  end

%% 3) Trust Boundaries

  flowchart LR
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

  U-->S
  S-->DB
  S-->OA
  S---L
  L-->R
  S-.reads.->SECRETS

  classDef boundary stroke-dasharray: 4 4;
  class BROWSER,HOST,SECRETS,CLOUD,OPENAI boundary

%% 4) Deployment Topology

  flowchart TD
  DEV[Dev Laptop] --> GH[GitHub Repo]
  GH -->|pull/clone| HOST[App Host]
  HOST -->|env vars| SECRETS[AGI_PUBKEY_B64 / AGI_KEY_B64 / AGI_LIC_B64]
  HOST --> DB[(Supabase Postgres)]
  HOST --> OA[OpenAI API]
  U[User] --> HOST

  classDef infra fill:#f1f8ff,stroke:#7fb3ff,color:#003b73;
  classDef ext fill:#fff9e6,stroke:#ffc056,color:#6c3b00;

  class HOST,DB infra
  class OA ext

  flowchart TD
  DEV[Dev Laptop] --> GH[GitHub Repo]
  GH -->|pull/clone| HOST[App Host]
  HOST -->|env vars| SECRETS[AGI_PUBKEY_B64 / AGI_KEY_B64 / AGI_LIC_B64]
  HOST --> DB[(Supabase Postgres)]
  HOST --> OA[OpenAI API]
  U[User] --> HOST

  classDef infra fill:#f1f8ff,stroke:#7fb3ff,color:#003b73;
  classDef ext fill:#fff9e6,stroke:#ffc056,color:#6c3b00;

  class HOST,DB infra
  class OA ext

%% 5) Data Model ERD

  erDiagram
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