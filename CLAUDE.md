# CLAUDE.md: EPAM powered InsureNdClaim

AI-assisted insurance claims MVP (GenAI Kata). A policyholder logs in, sees policies from fictional insurers, describes an incident to the **ClaimAssist** chat, answers follow-up questions, reviews an AI-drafted claim grounded in policy wording, submits it, and books an adjuster.

All insurers, adjusters, garages, policies and people are **fictional**. Never add real insurer names, real policy wording or real personal data.

## Commands

```bash
./run.sh                                   # start backend :8000 + frontend :5173 (installs deps)

# backend
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000  # API docs: http://127.0.0.1:8000/docs
pytest -q                                  # 42 tests, always runs in mock AI mode

# frontend
cd frontend
npm run dev                                # http://localhost:5173 (proxies /api → :8000)
npm run build                              # tsc --noEmit + vite build: run after any TS change
npm run test:chat                          # vitest+jsdom journey tests: needs backend running with LLM_PROVIDER=mock and a fresh DB
npm run test:e2e                           # Playwright (starts its own servers)
```

Reset demo data: stop the backend, delete `backend/data/`, start again (re-seeds). Demo logins: `daniel / Daniel@123`, `priya / Priya@123`.

## Layout

```
backend/app/
  main.py            FastAPI routes; create_app(settings, guidance) is the test seam
  auth.py            PBKDF2 passwords, session tokens, username/password rules, demo users
  models.py          Pydantic API schemas
  repositories.py    ALL SQL lives here (portable SQL; swap connect() for PostgreSQL)
  schema.sql, db.py  DDL + demo "migration" (rebuilds DB if old schema detected)
  seed.py            fictional insurers, adjusters, partners, policy templates, Daniel/Priya
  catalog.py         claim categories + keyword hints (single source of truth)
  scheduling.py      mock adjuster slots, appointment instructions/directions
  storage.py         upload validation (ext + magic bytes + size) and LocalStorage
  ai/
    service.py       SYSTEM_PROMPT (claim summary + photo analysis), FOLLOWUP_PROMPT, grounding, vision image loading
    assistant.py     SYSTEM prompt for policy Q&A; adjuster answers come from the DB, not the LLM
    chat.py          rule-based intent routing (no LLM)
    mock.py          deterministic fallback guidance + missing_items() gap detection
    providers.py     Anthropic + OpenAI-compatible clients (text + images)
    schemas.py       GuidanceRequest / ModelGuidance / ClaimGuidance contracts
frontend/src/
  api.ts             typed client + zod schemas + session token handling
  App.tsx            view state machine (login → dashboard → chat → claim)
  components/        LoginPage, Dashboard, AddPolicyForm, AdjusterDirectory, ChatAssistant, ClaimReview, ClaimDetail, AssistantPanel, ui
docs/                user stories, architecture (mermaid), test cases, deck (.pptx), user stories (.docx)
```

## Configuration

`backend/.env` (git-ignored; see `.env.example`): `LLM_PROVIDER=mock|anthropic|openai`, `LLM_API_KEY`, `LLM_MODEL` (default `claude-sonnet-4-5`), `LLM_BASE_URL`, `LLM_TIMEOUT_SECONDS`. Never print, log, commit or copy the key into other files.

## Non-negotiable AI guardrails

Any change to prompts, guidance or chat must keep these. Tests enforce most of them.

1. **Guidance, not decisions.** No coverage decisions, approvals, damage valuations, repair-cost estimates or fraud judgements.
2. **Grounding.** The model references cover only by codes from the supplied policy; `ground()` drops unknown codes and fills limits, deductibles and wording from the DB. Never let model text become a policy fact.
3. **Minimal context.** Send only the selected policy's terms, asset type/name, incident text, attachment metadata and photos. Never send the policyholder's name, other policies, credentials or secrets.
4. **Follow-up questions** are chosen from `missing_items()` keys only. The LLM may pick and rephrase, never invent topics, and never ask for medical, ID or bank details.
5. **Photos.** Observations describe visible damage only, are labelled AI, and are kept only for images actually sent. HEIC/oversized/mock mode must say "not analysed".
6. **Always works.** Every LLM path falls back to rules on timeout, HTTP error or invalid JSON, with a visible `fallback_reason`. Routing (`chat.py`) and the adjuster directory stay deterministic.
7. **Provenance.** UI tags each field as Policy wording / You provided / AI suggestion / System.

## Conventions

- Backend: keep SQL in `repositories.py`; validate with Pydantic; return user-safe `HTTPException` messages. Every new endpoint that touches user data takes `user=Depends(current_user)` and checks ownership (`owned_policy`, `ensure_self`); other users' resources return 404.
- Frontend: add new responses to `api.ts` with a zod schema (no `.default()` on schemas passed to `request`, which breaks type inference). Use `data-testid` on interactive elements used in tests. Tailwind utility classes plus the `card`/`btn-*`/`input`/`badge` components in `index.css`.
- Accessibility: labelled inputs, visible focus, `role="alert"`/`status` for errors and loading.
- Tests: fake providers must accept `complete(self, system, user, max_tokens=1500, images=None)`. Tests use `make_client(tmp_path, provider=..., login="daniel")`.
- Writing in UI and docs: plain language, no em-dashes in user-facing copy, label sample data as fictional.

## Gotchas

- `run.sh` and `npm run test:chat` need a **fresh DB** for the chat tests (they add a policy number that must be unique).
- Vitest chat tests: wait for an **enabled** Skip button (buttons are disabled while busy) and reset `session` between tests.
- Changing `schema.sql` columns on existing tables: extend the rebuild check in `db.init_db`, or old local DBs will break.
- `pkill -f uvicorn` inside a shell whose command line contains "uvicorn" kills that shell; use `kill $(pgrep -f "uvicorn app.main")`.

## Project skills and agents

- Skills (`.claude/skills/`): `run-checks`, `add-insurer-or-product`, `edit-ai-prompts`, `add-claim-category`, `reset-demo`.
- Source copies live in `claude-config/`; run `./claude-config/install.sh` to (re)install them into `.claude/`.
- Agents (`.claude/agents/`): `qa-tester`, `ai-guardrails-reviewer`, `security-reviewer`, `demo-presenter`.
