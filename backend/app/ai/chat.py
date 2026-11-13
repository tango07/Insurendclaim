"""Rule-based intent routing for the chat front door.

Routing is deterministic on purpose (reliable demo, no dependency on the model for navigation).
Free-text policy questions go to the assistant, and claim follow-ups to GuidanceService.follow_up.
"""
from __future__ import annotations

import re

from ..catalog import CATEGORIES

ADJUSTER = re.compile(r"\b(adjuster|adjustor|speak|talk|human|agent|person|someone|call me|appointment|inspect|inspection|meet)\b", re.I)
GARAGE = re.compile(r"\b(garage|repair ?shop|mechanic|body ?shop|repairer|who can (repair|fix)|which .* (repair|fix)|plumber|where .* (repair|fix))\b", re.I)
CLAIM = re.compile(r"\b(claim|file|report|lodge|submit)\b", re.I)
QUESTION = re.compile(r"\b(covered|cover|coverage|deductible|excess|limit|exclu\w*|policy say)\b", re.I)
INCIDENT = re.compile(r"\b(hit|crash\w*|dent\w*|scratch\w*|broke\w*|broken|stolen|theft|leak\w*|burst|damage\w*|flood\w*|fire|smashed|cracked|chip|rear.?ended)\b", re.I)


def detect(message: str, policy_type: str, insurer_short: str) -> dict:
    m = message.strip()
    intents = []
    incident = bool(INCIDENT.search(m)) or any(
        kw in m.lower() for k, v in CATEGORIES.items() if policy_type in v["policy_types"] for kw in v["keywords"] if len(kw) > 4)
    if CLAIM.search(m) or incident:
        intents.append("claim")
    if ADJUSTER.search(m):
        intents.append("adjuster")
    if GARAGE.search(m):
        intents.append("garage")
    if QUESTION.search(m) and not intents:
        intents.append("question")

    parts = []
    if incident:
        parts.append("I'm sorry to hear that. I hope everyone is safe.")
    if "adjuster" in intents:
        # Explicit request for a person: go straight to the adjuster list (slide step 3).
        parts.append("Sure, let me find a suitable adjuster for you.")
        return {"reply": " ".join(parts), "intents": intents, "actions": [{"id": "speak_adjuster", "label": "Speak with an adjuster"}],
                "looks_like_incident": incident and len(m) >= 15, "provider": "rules", "auto_action": "speak_adjuster"}
    if "claim" in intents or not intents:
        parts.append(f"I can help you start a claim with {insurer_short} now. I'll ask a few quick questions and then prepare a summary for you "
                     f"to check. Or I can connect you with a {insurer_short} adjuster.")
    if "garage" in intents:
        parts.append(f"You also asked about repairs, so I can show {insurer_short}'s partner repairers near you.")
    if intents == ["question"]:
        parts.append("Let me check your policy wording for that.")

    actions = []
    if intents != ["question"]:
        actions += [{"id": "start_claim", "label": "Start a claim"}, {"id": "speak_adjuster", "label": "Speak with an adjuster"}]
    if "garage" in intents:
        actions.append({"id": "find_garage", "label": "Show partner garages"})
    return {"reply": " ".join(parts), "intents": intents or ["unknown"], "actions": actions,
            "looks_like_incident": incident and len(m) >= 15, "provider": "rules", "auto_action": None}
