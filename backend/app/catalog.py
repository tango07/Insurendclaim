"""Claim category catalog. Single place to change categories, labels and keyword hints.

`keywords` are only used by the deterministic mock. The LLM is asked to pick a key
from the categories allowed for the selected policy type.
"""
from __future__ import annotations

CATEGORIES: dict[str, dict] = {
    "collision": {
        "label": "Collision",
        "policy_types": ["auto"],
        "keywords": ["rear-end", "rear end", "rear-ended", "collid", "crash", "hit ", "hit by", "bumper", "accident", "fender", "reversed into", "backed into", "dent"],
    },
    "glass": {
        "label": "Glass / windshield damage",
        "policy_types": ["auto"],
        "keywords": ["windshield", "windscreen", "chip", "glass", "window cracked", "cracked window"],
    },
    "theft": {
        "label": "Theft / burglary",
        "policy_types": ["auto", "home", "gadget"],
        "keywords": ["stolen", "theft", "steal", "broke into", "break-in", "burglar", "missing", "robbed"],
    },
    "vandalism": {
        "label": "Vandalism",
        "policy_types": ["auto", "home"],
        "keywords": ["vandal", "keyed", "graffiti", "slashed", "smashed"],
    },
    "weather": {
        "label": "Weather / natural event",
        "policy_types": ["auto", "home"],
        "keywords": ["hail", "storm", "wind", "tree fell", "fallen tree", "lightning", "cyclone"],
    },
    "flood": {
        "label": "Flood / surface water",
        "policy_types": ["auto", "home"],
        "keywords": ["flood", "flooded", "rising water", "waterlogged"],
    },
    "water": {
        "label": "Water damage (leak / burst pipe)",
        "policy_types": ["home"],
        "keywords": ["leak", "burst", "pipe", "water damage", "ceiling", "dripping", "overflow", "water heater"],
    },
    "fire": {
        "label": "Fire / smoke",
        "policy_types": ["auto", "home"],
        "keywords": ["fire", "smoke", "burn", "flames"],
    },
    "breakdown": {
        "label": "Breakdown / roadside assistance",
        "policy_types": ["auto"],
        "keywords": ["won't start", "wont start", "flat tyre", "flat tire", "battery", "tow", "breakdown", "broke down", "engine"],
    },
    "accidental_damage": {
        "label": "Accidental damage",
        "policy_types": ["home", "gadget"],
        "keywords": ["dropped", "spilled", "spill", "knocked over", "cracked screen", "broke"],
    },
    "liability": {
        "label": "Third-party liability",
        "policy_types": ["auto", "home"],
        "keywords": ["other driver", "their car", "injured", "neighbour", "neighbor", "someone slipped", "damaged their"],
    },
    "other": {
        "label": "Other / unsure",
        "policy_types": ["auto", "home", "gadget"],
        "keywords": [],
    },
}


def categories_for(policy_type: str) -> dict[str, str]:
    return {k: v["label"] for k, v in CATEGORIES.items() if policy_type in v["policy_types"]}


def label_for(key: str) -> str:
    return CATEGORIES.get(key, CATEGORIES["other"])["label"]
