"""Deterministic, rule-based guidance used when no LLM key is configured (or as a fallback).

Same input -> same output. It only references coverages/exclusions/conditions present in
the supplied PolicyContext, via the `tags` the seed data attaches to each clause.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..catalog import CATEGORIES
from .schemas import CoverageRef, ExclusionRef, GuidanceRequest, ModelGuidance

DATE_HINT = re.compile(r"\b(today|yesterday|tonight|last (night|week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
                       r"this morning|\d{1,2}(st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2})\b", re.I)
LOCATION_HINT = re.compile(r"\b(at|on|near|outside|in the|street|road|rd|avenue|ave|highway|parking|car park|lot|intersection|junction|kitchen|bathroom|bedroom|living room)\b", re.I)

DOCS_BY_CATEGORY = {
    "collision": ["Photos of all damaged areas and the scene", "Other driver's name, contact, plate and insurer details", "Repair estimate (a partner repair shop can send it directly)", "Police report number, if police attended or it was a hit-and-run"],
    "glass": ["Close-up photo of the chip/crack with a coin for scale", "Photo showing the whole windshield", "Glass shop quote or invoice"],
    "theft": ["Police report number", "List of stolen items with approximate value", "Proof of ownership (receipts, bank statements, photos)", "Photos of any damage from forced entry"],
    "vandalism": ["Police report number", "Photos of the damage", "Repair estimate"],
    "weather": ["Photos of the damage and the cause (e.g. fallen tree)", "Repair estimate", "Receipts for any emergency repairs"],
    "flood": ["Photos showing water level and damage", "Repair estimate", "Receipts for any emergency drying or clean-up"],
    "water": ["Photos of the damage and the leak source", "Plumber's report or invoice identifying the cause", "Receipts for emergency repairs or drying", "List of damaged belongings"],
    "fire": ["Fire service incident number, if attended", "Photos of the damage", "List of damaged items"],
    "breakdown": ["Location and description of the problem", "Tow / roadside invoice, if you paid yourself"],
    "accidental_damage": ["Photos of the damaged item", "Proof of purchase or value", "Repair quote"],
    "liability": ["Other party's name and contact details", "Photos of the scene", "Any written claim or letter you received from the other party"],
    "other": ["Photos of the damage", "Any receipts, quotes or reports related to the incident"],
}

STEPS_BY_CATEGORY = {
    "collision": ["Make sure everyone is safe; if anyone is hurt, call emergency services first", "Do not admit fault at the scene; exchange details with the other driver", "Get a repair estimate from a partner repair shop before repairs start", "An adjuster will contact you to confirm details and the estimate"],
    "glass": ["If the crack blocks your view, avoid driving and use roadside assistance", "Book a chip repair or replacement at a partner glass shop", "Upload the glass shop quote so an adjuster can review it"],
    "theft": ["Report the theft to the police within 48 hours and note the report number", "Write a list of what was taken and gather proof of ownership", "An adjuster will contact you to review the loss"],
    "vandalism": ["Report the vandalism to the police within 48 hours", "Photograph the damage before cleaning or repairing", "Get a repair estimate"],
    "weather": ["Take safe, reasonable steps to prevent further damage", "Photograph the damage before clean-up", "Keep receipts for emergency repairs"],
    "flood": ["Stay safe and do not enter flood water", "Photograph the damage and water level", "Talk to an adjuster: flood cover depends on the exact cause"],
    "water": ["Turn off the water supply or appliance if safe to do so", "Photograph the damage and the source of the leak", "Get a plumber to identify and fix the cause, and keep the report", "If a neighbour's unit is involved, note their contact details"],
    "fire": ["Make sure everyone is safe; contact the fire service if needed", "Do not enter the property until it is declared safe", "Photograph the damage once safe"],
    "breakdown": ["Move to a safe place and turn on hazard lights", "Call roadside assistance for towing to a partner repair shop", "Note: mechanical breakdown repairs may not be covered; roadside help is"],
    "accidental_damage": ["Stop using the item if it is unsafe", "Get a repair quote", "Keep the damaged item until an adjuster has reviewed the claim"],
    "liability": ["Do not admit liability or agree to pay the other party", "Note the other party's details and what happened", "Pass any letters or demands to your adjuster"],
    "other": ["Describe what happened in as much detail as you can", "Speak to an adjuster to confirm which cover may apply"],
}


def _classify(text: str, allowed: dict[str, str]) -> tuple[str, str]:
    t = f" {text.lower()} "
    scores = {k: sum(1 for kw in CATEGORIES[k]["keywords"] if kw in t) for k in allowed if k != "other"}
    best = max(scores, key=lambda k: scores[k], default="other") if scores else "other"
    hits = scores.get(best, 0)
    if hits == 0:
        return "other", "low"
    return best, "high" if hits >= 2 else "medium"


def _tags(clause_tags: str) -> set[str]:
    return {t.strip() for t in (clause_tags or "").split(",") if t.strip()}


def _summary(req: GuidanceRequest, label: str) -> str:
    first = re.split(r"(?<=[.!?])\s+", req.description.strip())[0]
    if len(first) > 220:
        first = first[:217].rstrip() + "..."
    parts = [f"{label} involving the insured {req.policy.asset_type} ({req.policy.asset_name})."]
    parts.append(f"Reported: {first.rstrip('.')}.")
    if req.incident_date:
        parts.append(f"Incident date: {req.incident_date}.")
    if req.incident_location:
        parts.append(f"Location: {req.incident_location}.")
    return " ".join(parts)


@dataclass(frozen=True)
class MissingItem:
    key: str
    missing: str     # wording for the "information that would help" list
    question: str    # conversational follow-up question for the chat
    why: str


def missing_items(req: GuidanceRequest, category: str, answered: set[str]) -> list[MissingItem]:
    """Ordered list of gaps in what the user has told us. Keys the user already answered are skipped."""
    d = req.description.lower()
    items: list[MissingItem] = []

    def add(key, missing, question, why):
        if key not in answered:
            items.append(MissingItem(key, missing, question, why))

    if not req.incident_date and not DATE_HINT.search(req.description):
        add("when", "Date and approximate time of the incident", "When did this happen? An approximate date and time is fine.",
            "Policies require notice within 30 days, and the date confirms the policy was active.")
    if not req.incident_location and not LOCATION_HINT.search(req.description):
        add("where", "Where the incident happened", "Where did it happen? A street, car park or room is enough.",
            "Location helps the adjuster and any repair partner.")
    if category in ("collision", "liability") and not re.search(r"\b(plate|registration|insurer|contact|details|hit.and.run|don'?t know who|no note)\b", d):
        add("other_party", "Other party's details (name, contact, plate and insurer), if someone else was involved",
            "Do you know who was involved? If so, share their name, plate number and insurer. If they left without a note, just say so.",
            "Needed to recover costs from the other party's insurer, or to treat it as a hit-and-run.")
    if category in ("collision", "liability", "fire") and not re.search(r"\b(injur|hurt|nobody|no one|noone)\w*", d):
        add("injuries", "Whether anyone was injured (yes/no only; please don't enter medical details here)",
            "Was anyone hurt? A simple yes or no is enough. Please don't share medical details here.",
            "Injuries change how the claim is handled and who needs to be involved.")
    if category in ("theft", "vandalism") or (category == "collision" and re.search(r"hit.and.run|left without|no note|drove off|don'?t know who", d)):
        if "police" not in d:
            add("police", "Police report number (policy condition: report within 48 hours)",
                "Have you reported this to the police? If yes, what's the report number?",
                "The policy asks for a police report within 48 hours for theft, vandalism and hit-and-run.")
    if category == "water" and not re.search(r"\b(pipe|appliance|washing machine|dishwasher|heater|neighbou?r|upstairs|roof)\b", d):
        add("water_source", "Source of the water (pipe, appliance, neighbouring unit, roof)",
            "Do you know where the water came from: a pipe, an appliance, a neighbouring flat or the roof?",
            "The source decides which part of the policy applies.")
    if category == "water" and not re.search(r"\b(sudden|burst|today|yesterday|this morning|last night)\b", d):
        add("water_sudden", "Whether the leak was sudden or developed over time (affects which terms apply)",
            "Did the leak start suddenly, or has it been building up over days or weeks?",
            "Sudden escape of water and gradual leaks are treated differently.")
    if category in ("collision", "vandalism", "weather", "glass") and req.policy.policy_type == "auto" and not re.search(r"\b(drivable|driveable|can drive|can't drive|cannot drive|undrivable|towed|still drives)\b", d):
        add("drivable", "Whether the car is safe to drive", "Is the car still safe to drive, or does it need towing?",
            "Decides whether roadside assistance or a mobile inspection is needed.")
    if category == "other":
        add("cause", "More detail about what caused the damage, so the right category can be identified",
            "Could you tell me a bit more about what caused the damage?", "So I can match it to the right part of your policy.")
    if not any(a.content_type.startswith("image/") for a in req.attachments):
        add("photos", "Photos of the damage", "Do you have photos of the damage? Attach them with the paperclip, or say 'later'.",
            "Photos speed up assessment, and the adjuster can see them before any call or visit.")
    return items


def mock_follow_up(req: GuidanceRequest, asked: set[str]) -> MissingItem | None:
    excerpts = " ".join(a.text_excerpt or "" for a in req.attachments)
    category, _ = _classify(f"{req.description} {excerpts}", req.policy.allowed_categories)
    items = missing_items(req, category, asked)
    return items[0] if items else None


def mock_guidance(req: GuidanceRequest, tag_index: dict[str, set[str]]) -> ModelGuidance:
    """`tag_index` maps clause code -> category tags (from DB). Kept out of the model context."""
    excerpts = " ".join(a.text_excerpt or "" for a in req.attachments)
    category, confidence = _classify(f"{req.description} {excerpts}", req.policy.allowed_categories)
    label = req.policy.allowed_categories.get(category, "Other / unsure")
    desc_l = req.description.lower()

    coverages = [CoverageRef(coverage_code=c.code, why_relevant=f"This cover lists events like '{label.lower()}', which matches your description.")
                 for c in req.policy.coverages if category in tag_index.get(c.code, set())]
    exclusions = [ExclusionRef(code=e.code, why_relevant="Could apply depending on the circumstances. An adjuster will confirm.")
                  for e in req.policy.exclusions if category in tag_index.get(e.code, set())]

    missing = [m.missing for m in missing_items(req, category, set(req.answered_keys))]

    docs = list(DOCS_BY_CATEGORY.get(category, DOCS_BY_CATEGORY["other"]))
    steps = list(STEPS_BY_CATEGORY.get(category, STEPS_BY_CATEGORY["other"]))
    for cond in req.policy.conditions:
        t = tag_index.get(cond.code, set())
        if not t or category in t:
            steps.append(f"Policy condition ({cond.code}): {cond.text}")

    limitations: list[str] = []
    needs_adjuster = category == "other" or confidence == "low"
    if not req.policy.wording_available or not req.policy.coverages:
        limitations.append("Policy wording for this policy is not available in the demo, so no coverage guidance can be given. Please contact an adjuster.")
        coverages, exclusions = [], []
        needs_adjuster = True
    elif not coverages:
        limitations.append("No coverage section in the sample policy clearly matches this description. An adjuster should confirm whether any cover applies.")
        needs_adjuster = True
    if category == "flood" and req.policy.policy_type == "home":
        limitations.append("Flood from outside the building is excluded, but escape of water from pipes is covered separately. The exact cause matters.")
        needs_adjuster = True

    return ModelGuidance(
        suggested_category=category,
        category_confidence=confidence,
        incident_summary=_summary(req, label),
        relevant_coverages=coverages,
        possible_exclusions=exclusions,
        missing_information=missing,
        documents_to_collect=docs[:8],
        next_steps=steps[:10],
        limitations=limitations,
        needs_adjuster_review=needs_adjuster,
    )
