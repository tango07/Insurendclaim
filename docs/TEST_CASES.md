# Test cases

Automated: `backend/tests/test_journey.py` (pytest, 20 tests) and `frontend/e2e/journey.spec.ts` (Playwright, 2 journeys).

| # | Scenario | Steps | Expected | Automated |
|---|----------|-------|----------|-----------|
| M1 | Select Daniel, view policies | Open app → click Daniel Reyes | Header shows Daniel; car, home and gadget policies with assets; "Mock mode" badge if no key | pytest + e2e |
| M2 | Policy details | Car policy → "View coverage, deductibles & exclusions" | Table of 6 covers with limits/deductibles, exclusions, conditions, "fictional" label | pytest + e2e |
| M3 | Create profile | Enter "Sam Lee", tick sample policies → Create | Lands on dashboard with 2 policies; untick → empty state | pytest |
| M4 | Correct asset | Car → "Get help with this vehicle" | Chat header shows Toyota Corolla, AUTO-DEMO-1001, Northstar | e2e (API mismatch: pytest) |
| M5 | Multiple attachments | Add a PNG + a TXT | Both listed with size | pytest + e2e |
| M6 | Invalid file | Add `bad.exe`, a 12 MB image, or a `.png` that's really text | Clear message; file not added / server 400 | pytest + e2e |
| M7 | Guidance structure | Use car Example 1 → Get claim guidance | Category Collision (high); summary; AUTO-COL with $500 deductible; exclusions; missing info; docs; steps; "image not analysed" note; disclaimer | pytest + e2e |
| M8 | Home water leak | Home → Example 1 | Category Water damage; HOME-WATER; gradual-leak exclusion listed | pytest |
| M9 | Missing policy wording | Gadget policy → describe dropped laptop | No coverages; limitation "wording not available… contact an adjuster" | pytest + e2e |
| M10 | Edit before submit | Change summary and steps; Submit disabled until confirm ticked | Submitted claim shows edited text; original description kept | pytest + e2e |
| M11 | Submitted claim | Submit | Claim number, status Submitted, timeline (2 events + 4 expected steps), appears in claims list | pytest + e2e |
| M12 | AI provider failure | Set `LLM_PROVIDER=anthropic` with an invalid key, or stop the network | Guidance still shown via mock, with the fallback reason | pytest (fake provider) |
| M13 | Invalid model output / invented terms | (fake provider) | Falls back, or unknown codes removed with a limitation | pytest |
| M14 | Backend down | Stop uvicorn, reload app | "Backend not reachable" error; intake errors offer "Fill in manually" | manual |
| M15 | Validation | Description under 15 chars; future date | Inline/API error message | pytest |
| M16 | Assistant | "What is my deductible?", "Is flood covered?" (home), gadget question | Answers cite codes; gadget says to contact an adjuster | pytest |
| M17 | Accessibility | Keyboard-only through the journey; screen reader on alerts | Focus rings, labelled inputs, focus moves to the review heading, alerts announced | manual |
| M18 | Responsive | 375 px width | Single-column layout, no horizontal scroll except the coverage table | manual |

## Iteration 2

Automated: `backend/tests/test_insurer_chat_adjuster.py` (11 tests), `frontend/src/__tests__/chat.integration.test.tsx` (vitest + jsdom against a running backend, slide journey end to end), `frontend/e2e/journey.spec.ts` (Playwright).

| # | Scenario | Expected | Automated |
|---|----------|----------|-----------|
| C1 | Insurer shown on each policy | Northstar (car), Harbourline (home), Brightleaf (gadget) with phone, email, hours | pytest + vitest |
| C2 | Slide step 2 message | Offers Start a claim, Speak with an adjuster, Show partner garages | pytest + vitest |
| C3 | Follow-ups | One question at a time, skippable, max 5, then the summary; answered topics not listed as missing | pytest + vitest |
| C4 | LLM follow-up guardrail | Invented topic or bank-detail question is rejected and the rules-based question is used | pytest |
| C5 | Adjuster list | 3 Northstar motor adjusters with office, specialisation, slots; the remote one has no on-site option | pytest + vitest |
| C6 | Contact validation | "12" shows an error; "+1 555 0199 123" is accepted | vitest (API: pytest) |
| C7 | On-site booking | Reference, directions with your location, instructions, shared photos, "told to expect you" | pytest + vitest |
| C8 | Video booking linked to claim | Demo Teams link; claim timeline "Adjuster appointment booked"; status In review | pytest + e2e |
| C9 | Double booking / cross-insurer adjuster / past slot | 409 / 400 / 409 | pytest |
| C10 | Partner garages | Sorted by distance, insurer-specific | pytest |
