---
name: add-insurer-or-product
description: Add a new fictional insurer, adjuster, repair partner, or policy product template (coverages, exclusions, conditions) to the InsureNdClaim seed data. Use when asked to add insurers, adjusters, garages, new policy types or extra sample policies.
---

# Add an insurer, adjuster, partner or product

All data lives in `backend/app/seed.py` and must be **clearly fictional** (names end with "(fictional)", use `.example` domains and `+1 555 01xx` phone numbers).

## Insurer
1. Append a tuple to `INSURERS`: `(id, name, short_name, claims_phone, claims_email, website, address, claims_hours, brand_color_hex)`.
2. Add its lines to `INSURER_LINES`, e.g. `"ins-newco": ["auto"]`. This drives the "Add a policy" insurer dropdown and validation.

## Adjuster
Append to `ADJUSTERS`: `(id, insurer_id, full_name, specialization, office_location, phone, email, languages, years, bio)`.
- `specialization` must match `SPECIALIZATION_FOR` in `repositories.py`: `motor` (auto), `property` (home), `devices` (gadget).
- An office starting with `"Remote team"` makes the adjuster remote-only (no on-site mode).

## Repair partner
Append to `REPAIR_PARTNERS`: `(id, insurer_id, name, kind, address, distance_km, rating, phone, services, hours)`.

## Product template (new policy type)
1. Create a template dict like `AUTO_POLICY` with `insurer_id`, `policy_type`, `product_name`, `status`, `summary`, `asset`, and `coverages`/`exclusions`/`conditions`.
2. Each clause has **tags**: comma-separated category keys from `app/catalog.py`. Tags drive mock guidance and follow-ups; untagged clauses are never suggested by the mock.
3. Register it in `TEMPLATES` and `ASSET_TYPES`, add the type to the relevant categories' `policy_types` in `catalog.py`, and mirror the options in `CATEGORY_OPTIONS` (`frontend/src/api.ts`) and `AddPolicyForm.tsx` (`TYPE_LABEL`, `FIELDS`, `ASSET_LABEL`).

## Apply
Seed only runs on an empty DB: stop the backend, delete `backend/data/`, restart. Then run the `run-checks` skill and add a pytest asserting the new item appears (see `tests/test_auth_and_policies.py`).
