"""Mock adjuster availability and appointment instructions.

Slots are generated deterministically (next 5 weekdays, fixed times, some pseudo-randomly
"already taken") minus slots actually booked in the DB. Swap `generate_slots` for a real
calendar integration later.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timedelta

SLOT_TIMES = ["09:30", "11:00", "14:00", "16:30"]
DURATION = {"audio": 20, "video": 30, "onsite": 45, "chat": 20}
MODE_LABEL = {"audio": "Phone call", "video": "Video call (Teams/Zoom)", "onsite": "On-site inspection", "chat": "Chat"}
REMOTE_ONLY = "Remote team"


def generate_slots(adjuster_id: str, booked: set[str], today: date | None = None, days: int = 5) -> list[str]:
    d = today or date.today()
    out: list[str] = []
    while len({s[:10] for s in out}) < days:
        d += timedelta(days=1)
        if d.weekday() >= 5:
            continue
        for t in SLOT_TIMES:
            key = f"{d.isoformat()}T{t}"
            busy = int(hashlib.sha1(f"{adjuster_id}{key}".encode()).hexdigest(), 16) % 3 == 0
            if not busy and key not in booked:
                out.append(key)
        if d > (today or date.today()) + timedelta(days=21):
            break
    return out


def slot_label(slot: str) -> str:
    dt = datetime.fromisoformat(slot)
    return dt.strftime("%a %d %b, %I:%M %p").replace(" 0", " ")


def allowed_modes(adjuster: dict) -> list[str]:
    return ["audio", "video", "chat"] if adjuster["office_location"].startswith(REMOTE_ONLY) else ["audio", "video", "onsite", "chat"]


def build_appointment_details(mode: str, adjuster: dict, policy_type: str, contact_phone: str, meeting_location: str | None,
                              claim: dict | None, n_photos: int) -> dict:
    instructions: list[str] = []
    link = directions = None
    if policy_type == "auto":
        instructions += ["Keep your driving licence and vehicle registration to hand (don't upload them here)."]
    if claim and claim.get("documents_to_collect"):
        instructions += [f"Have ready: {d}" for d in claim["documents_to_collect"][:5]]
    else:
        instructions += ["Have ready: photos of the damage from several angles, and any receipts, estimates or police report number."]
    if n_photos:
        instructions.append(f"Your {n_photos} uploaded file(s) have been shared with {adjuster['full_name']} ahead of the meeting.")

    if mode == "video":
        link = f"https://teams.example.invalid/meet/{uuid.uuid4().hex[:10]}"
        instructions.insert(0, "Join from a phone so you can show the damage on camera. The link opens Microsoft Teams (demo link, not a real meeting).")
    elif mode == "audio":
        instructions.insert(0, f"{adjuster['full_name']} will call you on {contact_phone}. Calls come from {adjuster['phone']}.")
    elif mode == "chat":
        instructions.insert(0, "The adjuster will message you in the EPAM powered InsureNdClaim portal at the booked time.")
    elif mode == "onsite":
        place = meeting_location or "the address you gave us"
        instructions.insert(0, f"{adjuster['full_name']} will come to {place} to inspect the {'vehicle' if policy_type == 'auto' else 'damage'}.")
        if policy_type == "auto":
            instructions.append("Park the car somewhere with space to walk around it and good light. Don't start repairs before the inspection.")
        else:
            instructions.append("Don't throw away damaged items or start permanent repairs before the inspection.")
        directions = (f"Inspection location: {place}. The adjuster will travel from {adjuster['office_location']}. "
                      f"If you need to move the meeting, call {adjuster['phone']} at least 2 hours before.")
    return {"instructions": instructions, "meeting_link": link, "directions": directions, "duration_minutes": DURATION[mode]}
