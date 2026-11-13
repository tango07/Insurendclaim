---
name: run-checks
description: Run the full InsureNdClaim verification suite (backend pytest, frontend type-check/build, chat journey tests) and report results. Use before a demo, before committing, or after any change to backend/app or frontend/src.
---

# Run checks

Run these in order and stop at the first failure to fix it.

1. **Backend tests** (always mock AI, isolated temp DBs):
   ```bash
   cd backend && source .venv/bin/activate && pytest -q
   ```
   Expect all tests to pass (42 at the time of writing).

2. **Frontend type-check and build**:
   ```bash
   cd frontend && npm run build
   ```

3. **Chat journey tests** (real backend, mock AI, fresh DB):
   ```bash
   cd backend && rm -f /tmp/ic-check.db && LLM_PROVIDER=mock INSURE_DB_PATH=/tmp/ic-check.db INSURE_UPLOAD_DIR=/tmp/ic-check-up \
     uvicorn app.main:app --port 8000 &
   sleep 3 && cd ../frontend && npm run test:chat
   kill $(pgrep -f "uvicorn app.main")
   ```

4. Optional: `npm run test:e2e` (Playwright; needs `npx playwright install chromium` once).

## Report

Summarise as: tests passed/failed per suite, the first failing test with its assertion message, and the likely cause. Don't claim success for a suite you didn't run.

## Common failures

- Fake provider `TypeError` about `images`: fakes must accept `images=None`.
- Chat test "Unable to find claim-review": the test didn't wait for an enabled Skip button, or the DB isn't fresh.
- 401 in new tests: use `make_client(...)`, which logs in as Daniel.
