# 🏗️ Architecture — AGIcyborg

## System Overview
_The high-level flow of the AGIcyborg runtime environment._

```mermaid
graph TD
  U[User 🧘‍♂️] -->|Reflects| S[Streamlit UI 🌿]
  S -->|Fetch / Save| DB[(Supabase Postgres)]
  S -->|Optional Guidance| OA[OpenAI Mentor 🧠]
  S -->|Load + Decrypt (in-memory)| RT[Encrypted Runtime 🔐]

  RT --> LIC[License Validation ✅]
  LIC -->|Ed25519 verify| PK[AGI_PUBKEY_B64]
  RT --> KEY[AGI_KEY_B64]:::secret
  RT --> ENC[runtime.bin.enc]:::binary

  DB --> PR[(reflection_prompts)]
  DB --> MI[(mentor_insights)]
  DB --> UR[(user_reflections)]

  classDef secret fill:#fde68a,stroke:#c2410c,color:#7c2d12
  classDef binary fill:#e5e7eb,stroke:#374151,color:#111827
```

## Data Model
_Entities and relationships used by the reflection engine._

```mermaid
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
```
