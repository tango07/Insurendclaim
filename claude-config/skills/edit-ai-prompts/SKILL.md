---
name: edit-ai-prompts
description: Safely change the LLM system or user prompts (claim summary, photo analysis, follow-up questions, policy Q&A) in InsureNdClaim, keeping the guardrails and output schema intact. Use whenever a prompt, model, temperature or AI output field is changed.
---

# Edit AI prompts safely

## Where the prompts are
| Use | System prompt | User prompt built at | Output schema |
|---|---|---|---|
| Claim summary + photos | `SYSTEM_PROMPT` in `backend/app/ai/service.py` | `GuidanceService.suggest()` (JSON of `GuidanceRequest`, images as vision blocks) | `ModelGuidance` in `ai/schemas.py` |
| Follow-up questions | `FOLLOWUP_PROMPT` in `ai/service.py` | `GuidanceService.follow_up()` (incident + `candidate_gaps`) | `{done, key, question}` |
| Policy Q&A | `SYSTEM` in `ai/assistant.py` | `answer()` (`Data:` JSON + `Question:`) | `{answer, sources}` |

The transport lives in `ai/providers.py` (temperature 0; vision timeout is 2.5× the base timeout).

## Rules when editing
1. Keep every guardrail in `CLAUDE.md` ("Non-negotiable AI guardrails"). Don't remove the lines about codes-only, no decisions/valuations/fraud, no sensitive data, JSON-only.
2. If you add an output field: add it to the prompt's schema text **and** to `ModelGuidance` (with a default), carry it through `ground()` into `ClaimGuidance`, add it to the zod `Guidance` schema in `frontend/src/api.ts` (`.optional()`, not `.default()`), and render it in `ClaimReview.tsx` with a `SourceTag`.
3. Anything the model says about policy terms or filenames must be validated against the request in `ground()`. Drop what isn't in the input.
4. Never add the policyholder's name or other policies to the user prompt.
5. Fallback must still work: a `ProviderError` or `ValidationError` returns mock guidance with `fallback_reason`.

## Verify
- `pytest -q` (fake-provider tests cover invalid JSON, invented codes, PII and photo grounding).
- Run one real call with the key in `backend/.env` (see `tests/test_image_analysis.py` for the request shape) and check: provider is `anthropic`, no `fallback_reason`, output fields populated.
- Ask the `ai-guardrails-reviewer` agent to review the diff.
