# Architecture

```
frontend/  React 18 + TypeScript + Vite + Tailwind, zod-validated API client
  src/App.tsx               view state (profiles → dashboard → intake → claim)
  src/api.ts                typed client + zod schemas
  src/components/*          ProfilePicker, Dashboard, ClaimIntake, ClaimDetail, AssistantPanel, ui
  e2e/journey.spec.ts       Playwright: Daniel's journey + missing-wording case
backend/   FastAPI + Pydantic v2 + SQLite
  app/main.py               routes, validation error shape, wiring (create_app for tests)
  app/models.py             API request/response schemas
  app/repositories.py       all SQL (swap for PostgreSQL here)
  app/schema.sql            portable DDL; app/seed.py fictional data
  app/storage.py            file validation + LocalStorage (Storage protocol → object storage later)
  app/catalog.py            claim categories (one place to change)
  app/ai/schemas.py         GuidanceRequest / ModelGuidance / ClaimGuidance
  app/ai/service.py         build context → provider or mock → validate → ground
  app/ai/providers.py       provider-neutral wrapper: Anthropic, OpenAI-compatible
  app/ai/mock.py            deterministic rule-based guidance
  app/ai/assistant.py       policy Q&A
```

## Data model

`insurers` 1─* `policies`, `adjusters`, `repair_partners`; `adjusters` 1─* `appointments` (→ policyholder, policy, optional claim).
`policyholders` 1─* `policies` 1─* `insured_assets`; `policies` 1─* `coverages` / `exclusions` / `policy_conditions`;
`claims` (→ policyholder, policy, asset) 1─* `claim_attachments`, 1─* `claim_events`.
Attachments are uploaded first (unlinked) and linked to the claim on submit. Each claim stores the user's verbatim description, the user-reviewed summary and steps, and a JSON snapshot of the original AI suggestion for audit.

## AI claim-intake path

```mermaid
sequenceDiagram
  participant U as Daniel (browser)
  participant FE as React app
  participant API as FastAPI
  participant DB as SQLite
  participant S as Storage
  participant G as GuidanceService
  participant L as LLM provider / Mock

  U->>FE: description, date, location, files
  FE->>FE: client-side type/size checks
  FE->>API: POST /api/attachments (multipart)
  API->>API: validate ext + magic bytes + size
  API->>S: save → storage_key
  API->>DB: insert unlinked attachments
  FE->>API: POST /api/claims/suggest {policy_id, asset_id, description, attachment_ids}
  API->>DB: load selected policy + asset only
  API->>G: GuidanceRequest (no name, no other policies)
  alt API key configured
    G->>L: system rules + JSON context
    L-->>G: JSON text
    G->>G: extract JSON → validate ModelGuidance
    Note over G: timeout / HTTP error / bad JSON → fallback to mock with reason
  else no key
    G->>L: mock_guidance (deterministic rules over clause tags)
  end
  G->>G: ground(): drop unknown codes, attach verbatim wording,<br/>limits & deductibles from DB, add limitations
  API-->>FE: ClaimGuidance
  U->>FE: edit category, summary, steps, docs; confirm
  FE->>API: POST /api/claims
  API->>DB: claim + link attachments + "submitted" events
  API-->>FE: ClaimOut (status, events, upcoming)
```

## Trust & safety controls

The model receives only the selected policy's terms, the asset type and name, the incident text and attachment metadata. It never receives the policyholder's name or other policies (covered by a test). Output is schema-validated, then **grounded**: coverage and exclusion codes not in the policy are removed, and limits, deductibles and wording come from the database, never the model. Missing wording or a non-active policy forces `needs_adjuster_review` and a limitation. Images are never "analysed". The UI tags every block as *Policy wording*, *You provided*, *AI suggestion* or *System*. Nothing is used for training; all data is fictional.

## Moving to production-ish

PostgreSQL: replace `db.connect()` and the `?` placeholders in `repositories.py`; the DDL is portable. Object storage: implement the `Storage` protocol (`save`/`read`). Adding a provider means implementing `complete(system, user)`.

## Iteration 2: chat-first intake and adjuster booking

```mermaid
sequenceDiagram
  participant U as Daniel
  participant C as ClaimAssist (React state machine)
  participant API as FastAPI
  participant G as GuidanceService
  participant L as Claude / rules
  U->>C: "My car was hit in a parking lot…"
  C->>API: POST /api/chat/intent
  API-->>C: reply + [Start a claim, Speak with an adjuster, Show garages]
  U->>C: Start a claim
  loop up to 5 questions
    C->>API: POST /api/claims/follow-up {description, asked_keys}
    API->>G: rules compute candidate gaps (keys)
    G->>L: pick + phrase one gap (LLM) — must return a known key
    L-->>C: question (+ why) — or done
    U->>C: answer / skip / attach photo
  end
  C->>API: POST /api/claims/suggest {description + answers, answered_keys}
  API-->>C: grounded ClaimGuidance → inline editable review → POST /api/claims
  U->>C: Speak with an adjuster
  C->>API: GET /api/policies/{id}/adjusters (insurer + line, generated slots − booked)
  U->>C: adjuster → slot → name/phone → mode (→ location)
  C->>API: POST /api/appointments
  API-->>C: reference, instructions, directions / meeting link, shared photos; claim event added
```

Routing (which flow you're in) is deterministic, so the demo never depends on the model to navigate. The LLM is used where language matters: phrasing follow-up questions, the claim summary, and policy Q&A. Each falls back to rules on any error. Slots come from `app/scheduling.py`: a deterministic mock calendar for the next 5 weekdays, minus confirmed bookings, with a partial unique index preventing double booking. Replace it with a real calendar API later.
