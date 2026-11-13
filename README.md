# EPAM powered InsureNdClaim: claims assistance MVP

Helps a policyholder (Daniel, 34, recently relocated) understand his cover, start a claim with AI-assisted guidance grounded in his policy, and see what happens next.

> **All data is fictional.** The insurers (Northstar Motor Mutual, Harbourline Home Insurance, Brightleaf Assurance), adjusters, garages and policy wording are invented for the demo. AI output is guidance only, never a coverage decision.

## Prerequisites
Python 3.10+, Node 18+ (tested with Python 3.10 and Node 22).

## Run it (two terminals)

```bash
# 1. Backend → http://127.0.0.1:8000  (API docs at /docs)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 2. Frontend → http://localhost:5173
cd frontend
npm install
npm run dev
```

Or run `./run.sh` from the project root to start both (macOS/Linux).

The database (`backend/data/insurendclaim.db`) is created and seeded on first start. To reset, delete `backend/data/`.

## Logins (fictional demo accounts)

| Username | Password | Profile |
|---|---|---|
| `daniel` | `Daniel@123` | Daniel Reyes: car, home, gadget policies |
| `priya` | `Priya@123` | Priya Natarajan: home policy |

Or use **Create account** on the login page. Passwords are stored as salted PBKDF2-SHA256 hashes in the `users` table, and sessions are random tokens (only a hash is stored), valid for 12 hours, in the `sessions` table. All data lives in SQLite at `backend/data/insurendclaim.db`: profiles, users, sessions, insurers, **adjusters**, partners, policies, claims and appointments. Open it with any SQLite browser.

## Demo script (≈5 min, follows the "User Journey" slide)
1. Log in as **daniel** (click the demo account, then Log in). Each policy card shows its **insurer** (Northstar for the car, Harbourline for the home) with claims phone, email and hours. The header badge shows the AI mode.
2. Click **Chat with ClaimAssist** → pick the **Toyota Corolla**.
3. Type: *"My car was hit in a parking lot. How do I claim, and which garage nearby can repair it?"* ClaimAssist offers **Start a claim**, **Speak with an adjuster** and **Show partner garages**.
4. **Start a claim**: it reuses your message, then asks follow-up questions one at a time (when, who was involved, injuries, police report, drivable…). Answer some, skip others, attach a photo with the 📎.
5. ClaimAssist then generates the **AI summary**: category, cover with policy wording, limits and deductibles, exclusions, missing info, next steps. Edit it inline, tick the confirmation and **Submit**.
6. **Speak with an adjuster**: "Sure, let me find a suitable adjuster for you." Choose **Maya Okafor**, pick a slot, enter your name and a fictional phone number, then choose **On-site inspection** and type a location.
7. You get a confirmation with a reference, an instruction note (documents and photos to keep ready), directions, and "Maya has been told to expect you and can already see your uploaded file".
8. Click **View claim status & timeline**. The status is now *In review*, with an "Adjuster appointment booked" event and the appointment card.
9. **+ Add a policy**: choose Car, Northstar, enter a policy number (e.g. `NSM-778812`) and "2019 Honda Jazz". It appears as a second car policy you can claim on. **Your adjusters** at the bottom lists every adjuster from the database. You can also type *"show me adjuster details"* in the chat, or ask the floating assistant *"Who is my adjuster?"*.
10. Edge case: **Get help with this device** on the Gadget laptop. The policy wording isn't loaded, so you get "contact an adjuster" rather than invented cover.

## Environment variables (`backend/.env`, see `.env.example`)

| Var | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `mock` | `mock`, `anthropic`, or `openai` (any OpenAI-compatible endpoint) |
| `LLM_API_KEY` | – | Provider key. If empty, the app runs in **mock mode** |
| `LLM_MODEL` | `claude-sonnet-4-5` / `gpt-4o-mini` | Model name |
| `LLM_BASE_URL` | provider default | Proxy or compatible endpoint (also sends a Bearer header) |
| `LLM_TIMEOUT_SECONDS` | `25` | Provider timeout; on timeout the app falls back to mock |
| `INSURE_DB_PATH`, `INSURE_UPLOAD_DIR` | `backend/data/…` | Storage locations |
| `INSURE_MAX_UPLOAD_MB`, `INSURE_MAX_FILES` | `10`, `10` | Upload limits |

Never commit `.env`; it is git-ignored.

## Mock mode
With no key, `app/ai/mock.py` produces deterministic guidance: keyword classification into a category, then coverages, exclusions and conditions selected by the tags on each clause in the sample policy. It passes through the same validation and grounding as real model output. The header badge shows the mode. Each guidance result says if it was produced by the mock, and gives the reason if it was a fallback after an AI failure.

## Tests
```bash
cd backend && pytest -q                                  # 38 API/service tests
# chat journey in a simulated browser (start the backend first with LLM_PROVIDER=mock)
cd frontend && npm run test:chat
cd frontend && npx playwright install chromium && npm run test:e2e   # starts both servers itself
```
See `docs/TEST_CASES.md` for the manual test cases and how they map to the automated ones.

## What's implemented / mocked / deferred
**Implemented (iteration 2):** fictional insurers on every policy; chat-first ClaimAssist with intent routing, AI follow-up questions (Claude picks and phrases from rule-detected gaps), and an inline editable AI summary; the adjuster journey from the slide (list → slot → name and phone → mode → location → confirmation with instructions, directions, a demo Teams link, shared photos and a claim timeline event); partner garages; appointments on the dashboard and claim page.
**Implemented (iteration 1):** profile select and create (initials placeholder), policy overview with coverages, limits, deductibles, exclusions and conditions; claim intake with multi-file upload and validation; structured AI guidance (Anthropic or OpenAI-compatible) with schema validation, grounding and fallback; review and edit; submission; status, timeline and next steps; claims list; policy Q&A assistant panel.
**Mocked:** AI when there's no key; adjuster calendars (deterministic generated slots); notifying the adjuster (stored with the booking, no email or SMS is sent); Teams/Zoom links (`teams.example.invalid`); garage distances; claim progression beyond booking.
**Photo analysis (iteration 4):** with an API key, uploaded JPG, PNG, WEBP or GIF photos (up to 5, ≤5 MB each) are sent to Claude's vision model. It describes visible damage per photo, flags photos that don't seem to match the description, and uses what it sees in the summary. Observations are labelled as AI and are never cost estimates or fraud judgements. HEIC and PDF contents aren't analysed. In mock mode, photos are acknowledged as "not analysed".
**Deferred:** auth, profile photo upload, a map/geolocation for garages, rescheduling or cancelling appointments, real notifications, adjuster console, editing a claim after submission.

## Assumptions (easy to change)
- **Username/password login** with server-side sessions. Every profile, policy, claim, attachment and appointment endpoint checks that it belongs to the logged-in user (other users' policies return 404). No password reset or lockout yet.
- **Adding a policy** copies the cover wording from the chosen insurer's sample product. The number isn't verified with the insurer, and the asset is labelled "Added by policyholder".
- **Currency USD, fictional city "Riverton".** Change these in `app/seed.py`.
- **Policies are issued by the insurer**, so users can't create them. New profiles can optionally get copies of the sample policies.
- **One asset per policy** in the seed data (the model supports many).
- **Claim categories** live in `app/catalog.py`, and clause-to-category tags live in the seed data. Edit either without code changes elsewhere.
- **"Upcoming" timeline steps are typical, not commitments**, and are labelled that way.
- **Uploads are linked on submit.** Orphaned uploads from abandoned drafts are kept (cleanup is deferred).
- **Each policy has exactly one insurer.** Adjusters are matched by insurer and line (motor, property or devices). Slots are Mon–Fri at 9:30, 11:00, 14:00 and 16:30 for the next 5 weekdays, with some marked busy.
- **Name and phone for the adjuster** are collected only at booking time, and the form says they're shared only with the adjuster. Use fictional values in the demo.
- **Older demo databases are rebuilt automatically** when the schema changes (a demo convenience, not a real migration).
- A third, **"wording pending" gadget policy** is seeded deliberately to demonstrate the missing-context path.

## Known limitations
No auth or multi-tenant isolation. SQLite with one connection per request is not tuned for concurrency. Mock classification is keyword-based, so unusual phrasing lands on "Other / unsure" (by design, with a limitation). The frontend category list mirrors `catalog.py` manually. HEIC files are accepted without a content check. Large PDFs aren't parsed.

## Future enhancements
Real image/PDF understanding with explicit "AI observed" labelling; map-based garage search with live availability; real calendar (Outlook/Google) and Teams/Zoom integration for adjusters; an adjuster console with status updates and notifications; editing and adding documents after submission; auth (OIDC); PostgreSQL and object storage; i18n; an evaluation set for guidance quality; and audit logs of prompts and responses with redaction.

More: `docs/ARCHITECTURE.md` (sequence diagram), `docs/USER_STORIES.md`.
