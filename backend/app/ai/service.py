"""Claim-guidance orchestration: build minimal context -> call provider (or mock) -> validate -> ground."""
from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from .. import repositories as repo
from ..catalog import categories_for
from ..config import Settings
from ..storage import Storage
from .mock import _classify, missing_items, mock_guidance
from .providers import LLMProvider, ProviderError, build_provider, extract_json
from .schemas import (AttachmentMeta, ClaimGuidance, ClauseCtx, CoverageCtx, CoverageInsight, ExclusionInsight,
                      GuidanceRequest, ModelGuidance, PolicyContext)

log = logging.getLogger("insurendclaim.ai")

SYSTEM_PROMPT = """You are a claims-intake assistant for a FICTIONAL demo insurer. You help a policyholder organise a claim.
Rules:
- Use ONLY the policy context provided. Never invent coverages, limits, deductibles, exclusions or conditions.
- Reference coverages and exclusions ONLY by the exact `code` values given. If nothing matches, return empty lists and add a limitation.
- If policy wording is missing or ambiguous, say so in `limitations` and set needs_adjuster_review=true.
- You give guidance only. Do NOT decide coverage, approve claims, value damage, or assess fraud. Use hedged wording ("may", "could").
- Photos may be attached as images, each labelled with its filename. For EACH image add an entry to `image_observations`:
  describe only what is clearly visible (which part is damaged, type of damage such as dent, scratch, crack, water stain,
  and the setting) in neutral, hedged language. Set matches_description to yes/partly/no/unclear depending on whether the
  photo appears to show the insured item and the described incident. Say so if the photo is blurry, too dark or unrelated.
- You may use what is visible to improve the summary and category, phrased as "photos appear to show ...".
- Never estimate repair costs, never judge severity in money terms, never suggest fraud or that the user is lying.
- Do not identify people or transcribe personal details (faces, ID or card numbers). Don't read out licence plates.
- PDFs are not visible to you; only plain-text excerpts of .txt files are provided. If no images are attached, image_observations is [].
- Never ask for medical details, ID numbers, or bank/card details.
- `suggested_category` MUST be one of the allowed category keys.
- Respond with a single JSON object only, no prose, matching this schema:
{"suggested_category": str, "category_confidence": "low"|"medium"|"high", "incident_summary": str (<=3 sentences, neutral, factual from the user's words),
 "relevant_coverages": [{"coverage_code": str, "why_relevant": str}], "possible_exclusions": [{"code": str, "why_relevant": str}],
 "missing_information": [str], "documents_to_collect": [str], "next_steps": [str] (at least 1), "limitations": [str], "needs_adjuster_review": bool,
 "image_observations": [{"filename": str, "observation": str, "matches_description": "yes"|"partly"|"no"|"unclear"}]}"""

VISION_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_VISION_BYTES = 5 * 1024 * 1024  # provider limit per image
MAX_VISION_IMAGES = 5


def load_images(attachments: list[dict], storage: Storage) -> tuple[list[dict], dict[str, str]]:
    """Base64 images for the vision model, plus a reason for each image that can't be sent."""
    import base64
    images, skipped = [], {}
    for a in attachments:
        if not a["content_type"].startswith("image/"):
            continue
        name = a["original_filename"]
        if a["content_type"] not in VISION_TYPES:
            skipped[name] = "this format (e.g. HEIC) can't be analysed. Please upload a JPG or PNG"
        elif a["size_bytes"] > MAX_VISION_BYTES:
            skipped[name] = "it's larger than 5 MB, so it wasn't analysed"
        elif len(images) >= MAX_VISION_IMAGES:
            skipped[name] = f"only the first {MAX_VISION_IMAGES} photos are analysed"
        else:
            try:
                images.append({"filename": name, "media_type": a["content_type"],
                               "data": base64.b64encode(storage.read(a["storage_key"])).decode()})
            except OSError:
                skipped[name] = "the file could not be read"
    return images, skipped


def build_context(conn, policy: dict, asset: dict) -> tuple[PolicyContext, dict[str, set[str]]]:
    """Only policy terms for the selected policy + asset. No policyholder name or other policies."""
    ctx = PolicyContext(
        policy_type=policy["policy_type"], product_name=policy["product_name"], policy_status=policy["status"],
        wording_available=policy["wording_available"], asset_type=asset["asset_type"], asset_name=asset["name"],
        coverages=[CoverageCtx(code=c["code"], name=c["name"], description=c["description"], limit_note=c["limit_note"],
                               deductible_amount=c["deductible_amount"]) for c in policy["coverages"]],
        exclusions=[ClauseCtx(code=e["code"], text=e["text"]) for e in policy["exclusions"]],
        conditions=[ClauseCtx(code=c["code"], text=c["text"]) for c in policy["conditions"]],
        allowed_categories=categories_for(policy["policy_type"]),
    )
    tags = {x["code"]: {t.strip() for t in x["tags"].split(",") if t.strip()}
            for x in policy["coverages"] + policy["exclusions"] + policy["conditions"]}
    return ctx, tags


def attachment_meta(attachments: list[dict], storage: Storage) -> list[AttachmentMeta]:
    out = []
    for a in attachments:
        excerpt = None
        if a["content_type"] == "text/plain":
            try:
                excerpt = storage.read(a["storage_key"])[:1500].decode("utf-8", errors="ignore")
            except OSError:
                excerpt = None
        out.append(AttachmentMeta(filename=a["original_filename"], content_type=a["content_type"],
                                  size_bytes=a["size_bytes"], text_excerpt=excerpt))
    return out


def _attachment_notes(atts: list[AttachmentMeta], skipped: dict[str, str] | None = None) -> list[str]:
    notes = []
    for a in atts:
        size = f"{a.size_bytes / 1024:.0f} KB" if a.size_bytes >= 1024 else f"{a.size_bytes} bytes"
        if a.content_type.startswith("image/") and a.analysed:
            notes.append(f"Image '{a.filename}' ({size}) was analysed by AI. See the photo observations; they describe visible damage only.")
        elif a.content_type.startswith("image/") and skipped and a.filename in skipped:
            notes.append(f"Received image '{a.filename}' ({size}), but {skipped[a.filename]}. Guidance uses your written description.")
        elif a.content_type.startswith("image/"):
            notes.append(f"Received image '{a.filename}' ({size}). Image content was not analysed; guidance uses your written description.")
        elif a.text_excerpt is not None:
            notes.append(f"Received text document '{a.filename}' ({size}). Its text was read and considered.")
        else:
            notes.append(f"Received document '{a.filename}' ({size}). Contents were not read; guidance uses your written description.")
    return notes


def ground(raw: ModelGuidance, req: GuidanceRequest, provider: str, fallback_reason: str | None,
           skipped: dict[str, str] | None = None) -> ClaimGuidance:
    """Drop anything not present in the policy context and attach verbatim policy facts."""
    cov_by_code = {c.code: c for c in req.policy.coverages}
    exc_by_code = {e.code: e for e in req.policy.exclusions}
    limitations = list(raw.limitations)
    needs_adjuster = raw.needs_adjuster_review

    category = raw.suggested_category if raw.suggested_category in req.policy.allowed_categories else "other"
    if category != raw.suggested_category:
        limitations.append("The suggested category was not valid for this policy type and was reset to 'Other / unsure'.")

    coverages, dropped = [], 0
    for ref in raw.relevant_coverages:
        c = cov_by_code.get(ref.coverage_code)
        if not c:
            dropped += 1
            continue
        if any(x.coverage_code == c.code for x in coverages):
            continue
        coverages.append(CoverageInsight(coverage_code=c.code, coverage_name=c.name, why_relevant=ref.why_relevant,
                                         policy_wording=c.description, limit_note=c.limit_note, deductible_amount=c.deductible_amount))
    exclusions = []
    for ref in raw.possible_exclusions:
        e = exc_by_code.get(ref.code)
        if not e:
            dropped += 1
            continue
        exclusions.append(ExclusionInsight(code=e.code, policy_wording=e.text, why_relevant=ref.why_relevant))
    if dropped:
        limitations.append(f"{dropped} reference(s) to policy terms not found in the sample policy were removed.")

    if not req.policy.wording_available or not req.policy.coverages:
        coverages, exclusions = [], []
        msg = "Policy wording for this policy is not available, so no coverage guidance can be given. Please contact an adjuster."
        if not any("not available" in lim for lim in limitations):
            limitations.insert(0, msg)
        needs_adjuster = True
    analysed = {a.filename for a in req.attachments if a.analysed}
    observations = [o for o in raw.image_observations if o.filename in analysed]  # only images actually sent
    if any(o.matches_description == "no" for o in observations):
        limitations.append("At least one photo may not show the insured item or the described incident. An adjuster will review it.")
        needs_adjuster = True
    if req.policy.policy_status != "active":
        limitations.append(f"This policy's status is '{req.policy.policy_status}'. An adjuster needs to confirm it was in force on the incident date.")
        needs_adjuster = True

    return ClaimGuidance(
        suggested_category=category, suggested_category_label=req.policy.allowed_categories.get(category, "Other / unsure"),
        category_confidence=raw.category_confidence, incident_summary=raw.incident_summary,
        relevant_coverages=coverages, possible_exclusions=exclusions,
        missing_information=raw.missing_information, documents_to_collect=raw.documents_to_collect,
        next_steps=raw.next_steps, limitations=limitations, needs_adjuster_review=needs_adjuster,
        attachment_notes=_attachment_notes(req.attachments, skipped), image_observations=observations,
        provider=provider, fallback_reason=fallback_reason,
    )


class GuidanceService:
    def __init__(self, settings: Settings, provider: LLMProvider | None = None, use_env_provider: bool = True):
        self.settings = settings
        self.provider = provider if provider is not None else (build_provider(settings) if use_env_provider else None)

    @property
    def mode(self) -> str:
        return self.provider.name if self.provider else "mock"

    def suggest(self, req: GuidanceRequest, tag_index: dict[str, set[str]], images: list[dict] | None = None,
                skipped: dict[str, str] | None = None) -> ClaimGuidance:
        if self.provider is None:
            return ground(mock_guidance(req, tag_index), req, "mock", None)
        images = images or []
        sent = {i["filename"] for i in images}
        req_ai = req.model_copy(update={"attachments": [a.model_copy(update={"analysed": a.filename in sent}) for a in req.attachments]})
        try:
            text = self.provider.complete(SYSTEM_PROMPT, "Context and incident (JSON):\n" + req_ai.model_dump_json(indent=1),
                                          max_tokens=2000, images=images or None)
            raw = ModelGuidance.model_validate(extract_json(text))
            return ground(raw, req_ai, self.provider.name, None, skipped)
        except (ProviderError, ValidationError) as e:
            reason = str(e) if isinstance(e, ProviderError) else "AI response did not match the expected structure"
            log.warning("AI guidance failed, using rule-based fallback: %s", reason)
            return ground(mock_guidance(req, tag_index), req, "mock", f"{reason}. Showing rule-based guidance instead.")

    def follow_up(self, req: GuidanceRequest, asked: list[str], max_questions: int = 5) -> dict:
        """Next clarifying question for the chat. Rules find the gaps; the LLM (if any) picks and phrases one."""
        asked_set = set(asked)
        if len(asked_set) >= max_questions:
            return {"done": True, "provider": self.mode}
        excerpts = " ".join(a.text_excerpt or "" for a in req.attachments)
        category, _ = _classify(f"{req.description} {excerpts}", req.policy.allowed_categories)
        gaps = missing_items(req, category, asked_set)
        if not gaps:
            return {"done": True, "provider": self.mode}
        first = {"done": False, "key": gaps[0].key, "question": gaps[0].question, "why": gaps[0].why}
        if self.provider is None:
            return first | {"provider": "mock"}
        try:
            payload = {"incident_so_far": req.description, "asset": req.policy.asset_name, "policy_type": req.policy.policy_type,
                       "candidate_gaps": [{"key": g.key, "needed": g.missing, "why": g.why} for g in gaps]}
            raw = extract_json(self.provider.complete(FOLLOWUP_PROMPT, json.dumps(payload), max_tokens=300))
            key, question = raw.get("key"), str(raw.get("question", "")).strip()
            if raw.get("done") is True:
                return {"done": True, "provider": self.provider.name}
            gap = next((g for g in gaps if g.key == key), None)
            if not gap or not (5 < len(question) <= 300):
                raise ProviderError("follow-up did not match a known gap")
            return {"done": False, "key": gap.key, "question": question, "why": gap.why, "provider": self.provider.name}
        except ProviderError as e:
            log.warning("follow-up via AI failed, using rules: %s", e)
            return first | {"provider": "mock"}


FOLLOWUP_PROMPT = """You are a friendly claims-intake assistant for a FICTIONAL demo insurer, chatting with a policyholder.
Pick the single most useful next question from `candidate_gaps` (prefer safety and policy-condition items) and phrase it warmly
in at most 2 short sentences. Never ask for medical details, ID numbers or bank details. If the description already answers every
gap well enough, return done=true. Respond with JSON only: {"done": bool, "key": "<one candidate key>", "question": "<text>"}"""


def build_request(conn, storage: Storage, policy: dict, asset: dict, description: str, incident_date, incident_location,
                  attachment_ids: list[str], answered_keys: list[str] | None = None) -> tuple[GuidanceRequest, dict[str, set[str]]]:
    ctx, tags = build_context(conn, policy, asset)
    atts = attachment_meta(repo.get_attachments(conn, attachment_ids), storage)
    req = GuidanceRequest(description=description, incident_date=str(incident_date) if incident_date else None,
                          incident_location=incident_location, policy=ctx, attachments=atts, answered_keys=answered_keys or [])
    return req, tags


def dump(g: ClaimGuidance) -> dict:
    return json.loads(g.model_dump_json())
