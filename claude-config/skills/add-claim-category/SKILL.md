---
name: add-claim-category
description: Add or change a claim category (e.g. "electrical fault", "pet damage") across catalog, mock rules, follow-up questions, policy clause tags and the frontend dropdown. Use when the user wants new incident types recognised.
---

# Add a claim category

1. **Catalog**: add `key: {label, policy_types, keywords}` to `CATEGORIES` in `backend/app/catalog.py`. Keywords are lowercase substrings used by the mock classifier and chat intent.
2. **Clause tags**: in `backend/app/seed.py`, add the key to the `tags` of every coverage, exclusion and condition that applies. Without tags the mock won't suggest any cover.
3. **Mock guidance**: add entries to `DOCS_BY_CATEGORY` and `STEPS_BY_CATEGORY` in `backend/app/ai/mock.py`.
4. **Follow-up gaps**: if the category needs specific facts, add an `add(key, missing, question, why)` rule in `missing_items()` (`ai/mock.py`). Keys must be unique and stable; questions must never ask for medical, ID or bank details.
5. **Frontend**: add `[key, label]` to `CATEGORY_OPTIONS` in `frontend/src/api.ts` for each policy type.
6. **Tests**: add a pytest like `test_home_water_leak` in `tests/test_journey.py` asserting the category, the expected coverage code and any exclusion.
7. Reset the DB (seed tags changed), then run the `run-checks` skill.
