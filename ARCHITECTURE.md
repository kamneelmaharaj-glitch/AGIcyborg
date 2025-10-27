# AGIcyborg — Architecture

> High-level view of the runtime, data flow, trust boundaries, and deployment.
> All diagrams use GitHub-compatible Mermaid.

---

%% 1) System Overview

```mermaid
flowchart TD
  %% ---------------------------
  %%  System Overview Diagram
  %% ---------------------------

  %% Nodes
  U[User / Browser]
  S[Streamlit UI]
  DB[(Supabase<br/>Postgres)]
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
  S -->|Fetch / Save| DB
  S -->|Optional guidance| OA
  S -->|Load & decrypt (in-memory)| RT

  %% 2) Runtime load & verification
  RT -->|validate| LIC
  LIC -->|ed25519 verify with| PK
  RT -->|decrypt using| KEY
  RT -->|reads| BIN

  %% 3) Data groupings (tables inside DB)
  DB --- PR
  DB --- MI
  DB --- UR

  %% Optional styling (GitHub-safe)
  classDef db fill:#eef5ff,stroke:#6b93d6,color:#102a43,stroke-width:1px;
  classDef rt fill:#fff5e6,stroke:#d17a00,color:#3b2f00,stroke-width:1px;
  classDef sec fill:#fde8ea,stroke:#c2414b,color:#6a041d,stroke-width:1px;

  class DB,PR,MI,UR db;
  class RT rt;
  class LIC,PK,KEY, BIN sec;

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