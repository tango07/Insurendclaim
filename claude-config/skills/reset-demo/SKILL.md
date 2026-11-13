---
name: reset-demo
description: Reset InsureNdClaim to a clean demo state (fresh seeded database, cleared uploads) and confirm the app is ready to present. Use before a demo or when test data clutters the dashboard.
---

# Reset the demo

1. Stop the running app (Ctrl+C in the `./run.sh` terminal, or `kill $(pgrep -f "uvicorn app.main")`).
2. Delete local data: `rm -rf backend/data` (removes the SQLite DB and uploads; seed data is recreated on start).
3. Start again: `./run.sh`.
4. Confirm:
   - `curl -s http://127.0.0.1:8000/api/health` shows `"status":"ok"` and the expected `ai_mode` (`anthropic` if `backend/.env` has a key, else `mock`).
   - Log in at http://localhost:5173 as `daniel / Daniel@123`: 3 policies (Northstar car, Harbourline home, Brightleaf gadget), 1 example claim `CLM-DEMO-0001`, no appointments.
5. Tell the user the demo is ready, and which AI mode is active.

Never delete `backend/.env` or print its contents.
