"""Fictional sample data. NOT a real insurer, NOT real policy wording.

Everything here is invented for the InsureNdClaim demo. Edit freely.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

DEMO_INSURER = "Fictional Demo Mutual (sample data only)"
DANIEL_ID = "ph-daniel"


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


INSURERS = [
    # id, name, short_name, claims_phone, claims_email, website, address, hours, colour
    ("ins-northstar", "Northstar Motor Mutual (fictional)", "Northstar", "+1 555 0100 200", "claims@northstar.example",
     "https://northstar.example", "400 Harbour Road, Riverton (fictional)", "24/7 claims line; adjusters Mon–Fri 9:00–17:30", "#1d4ed8"),
    ("ins-harbourline", "Harbourline Home Insurance (fictional)", "Harbourline", "+1 555 0100 300", "homeclaims@harbourline.example",
     "https://harbourline.example", "18 Elm Court, Riverton (fictional)", "Mon–Sat 8:00–20:00; emergency water line 24/7", "#0f766e"),
    ("ins-brightleaf", "Brightleaf Assurance (fictional)", "Brightleaf", "+1 555 0100 400", "help@brightleaf.example",
     "https://brightleaf.example", "Online-only insurer (fictional)", "Mon–Fri 9:00–18:00", "#b45309"),
]

ADJUSTERS = [
    # id, insurer, name, specialization, office, phone, email, languages, years, bio
    ("adj-maya", "ins-northstar", "Maya Okafor", "motor", "Northstar Riverton Claims Centre, 400 Harbour Road",
     "+1 555 0101 011", "maya.okafor@northstar.example", "English, French", 9, "Collision and parking-damage claims; partner-garage estimates."),
    ("adj-tom", "ins-northstar", "Tomás Ferreira", "motor", "Northstar Eastside Inspection Bay, 77 Mill Lane",
     "+1 555 0101 022", "tomas.ferreira@northstar.example", "English, Portuguese, Spanish", 6, "On-site vehicle inspections, theft and vandalism."),
    ("adj-lena", "ins-northstar", "Lena Park", "motor", "Remote team (video/phone only)",
     "+1 555 0101 033", "lena.park@northstar.example", "English, Korean", 4, "Glass, roadside and quick-settle motor claims."),
    ("adj-sam", "ins-harbourline", "Samir Haddad", "property", "Harbourline Riverton Office, 18 Elm Court",
     "+1 555 0102 011", "samir.haddad@harbourline.example", "English, Arabic", 11, "Escape-of-water and storm damage in apartments."),
    ("adj-grace", "ins-harbourline", "Grace Liu", "property", "Harbourline Riverton Office, 18 Elm Court",
     "+1 555 0102 022", "grace.liu@harbourline.example", "English, Mandarin", 7, "Contents, theft and liability claims."),
    ("adj-ola", "ins-brightleaf", "Ola Nilsen", "devices", "Remote team (video/phone/chat)",
     "+1 555 0103 011", "ola.nilsen@brightleaf.example", "English, Norwegian", 5, "Laptops, phones and accidental-damage claims."),
]

REPAIR_PARTNERS = [
    # id, insurer, name, kind, address, km, rating, phone, services, hours
    ("rp-1", "ins-northstar", "Riverton Auto Body & Paint", "garage", "22 Foundry Street, Riverton", 1.8, 4.7, "+1 555 0110 001",
     "Collision repair, bumper & panel work, paint; sends estimates directly to Northstar", "Mon–Sat 8:00–18:00"),
    ("rp-2", "ins-northstar", "QuickFix Motors Eastside", "garage", "5 Mill Lane, Riverton", 3.4, 4.4, "+1 555 0110 002",
     "Mechanical and body repair, courtesy car available", "Mon–Fri 7:30–17:30"),
    ("rp-3", "ins-northstar", "ClearView Glass Riverton", "glass", "90 Station Road, Riverton", 2.6, 4.8, "+1 555 0110 003",
     "Windshield chip repair (no deductible), replacement, mobile service", "Mon–Sat 8:00–17:00"),
    ("rp-4", "ins-harbourline", "Riverton Emergency Plumbing", "plumber", "3 Canal Walk, Riverton", 1.2, 4.6, "+1 555 0120 001",
     "24/7 leak detection, burst pipes, written cause reports", "24/7"),
    ("rp-5", "ins-harbourline", "DryRight Restoration", "restoration", "41 Quarry Road, Riverton", 4.9, 4.5, "+1 555 0120 002",
     "Water damage drying, ceiling & plaster repair", "Mon–Fri 8:00–18:00"),
    ("rp-6", "ins-brightleaf", "FixPoint Devices", "device_repair", "Riverton Mall, Unit 14", 2.1, 4.3, "+1 555 0130 001",
     "Laptop screen & keyboard repair, data-safe handling", "Daily 10:00–20:00"),
]

AUTO_POLICY = {
    "insurer_id": "ins-northstar",
    "policy_type": "auto",
    "product_name": "Demo Motor Comprehensive",
    "status": "active",
    "summary": "Comprehensive car cover: collision, theft, fire, weather, glass, third-party liability, roadside and rental car.",
    "asset": {
        "asset_type": "vehicle",
        "name": "2021 Toyota Corolla Hatchback",
        "details": {"Registration": "DEMO-4821 (fictional)", "Colour": "Silver", "Usage": "Private / commuting", "Garaged at": "Riverton (fictional)"},
    },
    "coverages": [
        ("AUTO-COL", "Collision", "Damage to your car from a collision with another vehicle or object, regardless of fault. Settled at repair cost or actual cash value, whichever is lower.", 25000, "Up to actual cash value of the vehicle, max $25,000", 500, "collision,vandalism"),
        ("AUTO-COMP", "Comprehensive (non-collision)", "Damage to or loss of your car from theft, attempted theft, fire, vandalism, falling objects, hail, storm and flood.", 25000, "Up to actual cash value of the vehicle, max $25,000", 250, "theft,fire,vandalism,weather,flood"),
        ("AUTO-GLASS", "Glass and windshield", "Repair or replacement of windshield and window glass. Chip repairs at a partner glass shop have no deductible.", 1500, "Up to $1,500 per incident", 100, "glass"),
        ("AUTO-TPL", "Third-party liability", "Your legal liability for injury to other people or damage to their property arising from use of your car.", 300000, "$300,000 per incident", 0, "liability,collision"),
        ("AUTO-ROAD", "Roadside assistance", "Towing to the nearest partner repair shop (up to 50 km), jump start, flat-tyre change and lockout help.", 150, "Up to $150 per call-out, 4 call-outs per year", 0, "breakdown,collision"),
        ("AUTO-RENT", "Rental car reimbursement", "Rental car while your car is being repaired for a covered claim.", 1200, "$40 per day, max 30 days", 0, "collision,theft,fire,weather,flood,vandalism"),
    ],
    "exclusions": [
        ("AUTO-EX-DUI", "Any loss while the driver is under the influence of alcohol or drugs above the legal limit.", "collision,liability"),
        ("AUTO-EX-LIC", "Any loss while the car is driven by a person without a valid licence.", "collision,liability"),
        ("AUTO-EX-COMM", "Use for paid ride-share, delivery or other commercial purposes.", "collision,liability"),
        ("AUTO-EX-WEAR", "Wear and tear, mechanical or electrical breakdown, and tyre damage from punctures (roadside help still applies).", "breakdown"),
        ("AUTO-EX-KEYS", "Theft where the keys were left in or on the unlocked car.", "theft"),
        ("AUTO-EX-RACE", "Racing, track days or speed tests.", "collision"),
    ],
    "conditions": [
        ("AUTO-C-NOTIFY", "Notify us as soon as reasonably possible, and within 30 days of the incident.", ""),
        ("AUTO-C-POLICE", "Report theft, attempted theft, vandalism and hit-and-run incidents to the police within 48 hours and keep the report number.", "theft,vandalism,collision"),
        ("AUTO-C-LIAB", "Do not admit fault or agree to pay another party at the scene. Exchange names, contact, plate and insurer details.", "collision,liability"),
        ("AUTO-C-MITIGATE", "Take reasonable steps to prevent further damage (e.g. do not keep driving a car that is unsafe).", "collision,glass,weather,flood,fire"),
        ("AUTO-C-REPAIR", "Get our approval of the repair estimate before non-emergency repairs begin. Partner repair shops can send estimates directly.", "collision,glass,vandalism,weather,fire"),
    ],
}

HOME_POLICY = {
    "insurer_id": "ins-harbourline",
    "policy_type": "home",
    "product_name": "Demo Home & Contents",
    "status": "active",
    "summary": "Building and contents cover for your apartment: fire, theft, sudden water damage, storm, accidental damage, liability and temporary accommodation.",
    "asset": {
        "asset_type": "property",
        "name": "Apartment 4B, 12 Sample Street, Riverton",
        "details": {"Type": "2-bedroom apartment (3rd floor)", "Occupancy": "Owner-occupied", "Built": "2009", "Address": "Fictional address"},
    },
    "coverages": [
        ("HOME-BLD", "Building (dwelling)", "Damage to the structure of your apartment, fixtures and fittings from fire, storm, theft, vandalism and sudden escape of water.", 250000, "Up to $250,000", 1000, "fire,weather,water,vandalism,theft"),
        ("HOME-CNT", "Contents (personal property)", "Loss of or damage to your belongings at home from the same insured events as Building cover. Items over $2,000 must be listed.", 50000, "Up to $50,000; single items max $2,000 unless listed", 500, "fire,weather,water,theft,vandalism"),
        ("HOME-WATER", "Sudden escape of water", "Sudden and accidental discharge of water from pipes, appliances or a neighbouring unit. Includes cost of tracing the leak.", 20000, "Up to $20,000 per incident (within Building limit)", 1000, "water"),
        ("HOME-ACC", "Accidental damage", "Accidental damage to TVs, computers and fixed glass at home.", 5000, "Up to $5,000 per incident", 250, "accidental_damage"),
        ("HOME-LOU", "Loss of use / temporary accommodation", "Reasonable extra costs of temporary accommodation if your home is unliveable after a covered event.", 10000, "Up to $10,000 or 12 months", 0, "fire,water,weather"),
        ("HOME-LIAB", "Personal liability", "Your legal liability for injury to other people or damage to their property, at home or worldwide.", 300000, "$300,000 per incident", 0, "liability,water"),
    ],
    "exclusions": [
        ("HOME-EX-FLOOD", "Flood or rising surface water from outside the building (escape of water from pipes is covered separately).", "flood,water,weather"),
        ("HOME-EX-GRAD", "Gradual leaks, seepage, damp, rot or mould that developed over time (more than 14 days).", "water"),
        ("HOME-EX-WEAR", "Wear and tear, maintenance issues and gradual deterioration.", "water,accidental_damage"),
        ("HOME-EX-VACANT", "Theft or water damage while the home has been unoccupied for more than 60 consecutive days.", "theft,water"),
        ("HOME-EX-QUAKE", "Earthquake.", "weather"),
        ("HOME-EX-INTENT", "Deliberate damage by you or someone living with you.", "vandalism,accidental_damage"),
    ],
    "conditions": [
        ("HOME-C-NOTIFY", "Notify us as soon as reasonably possible, and within 30 days of discovering the damage.", ""),
        ("HOME-C-POLICE", "Report theft, burglary and vandalism to the police within 48 hours and keep the report number.", "theft,vandalism"),
        ("HOME-C-MITIGATE", "Take reasonable steps to stop further damage (e.g. turn off the water supply, cover broken windows). Keep receipts for emergency repairs.", "water,weather,fire,accidental_damage"),
        ("HOME-C-PROOF", "Keep damaged items until we have seen them, and provide proof of ownership or value where available.", "theft,fire,water,accidental_damage,weather"),
    ],
}

# Deliberately incomplete: wording not loaded. Demonstrates the "missing policy context" path.
GADGET_POLICY = {
    "insurer_id": "ins-brightleaf",
    "policy_type": "gadget",
    "product_name": "Demo Gadget Protect (wording pending)",
    "status": "pending",
    "summary": "Recently purchased add-on. Full policy wording has not been loaded into the demo yet.",
    "wording_available": False,
    "asset": {
        "asset_type": "device",
        "name": "14\" Laptop (work)",
        "details": {"Serial": "DEMO-SN-0091 (fictional)", "Purchased": "2026-09"},
    },
    "coverages": [],
    "exclusions": [],
    "conditions": [],
}


def _insert_policy(conn: sqlite3.Connection, holder_id: str, tpl: dict, number: str, start: datetime) -> tuple[str, str]:
    pid = _id()
    conn.execute(
        "INSERT INTO policies (id, policyholder_id, insurer_id, policy_number, policy_type, product_name, status, start_date, end_date, summary, wording_available) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (pid, holder_id, tpl["insurer_id"], number, tpl["policy_type"], tpl["product_name"], tpl["status"], start.date().isoformat(),
         (start + timedelta(days=365)).date().isoformat(), tpl["summary"], 1 if tpl.get("wording_available", True) else 0),
    )
    aid = _id()
    a = tpl["asset"]
    conn.execute("INSERT INTO insured_assets (id, policy_id, asset_type, name, details) VALUES (?,?,?,?,?)",
                 (aid, pid, a["asset_type"], a["name"], json.dumps(a["details"])))
    for code, name, desc, limit, limit_note, ded, tags in tpl["coverages"]:
        conn.execute(
            "INSERT INTO coverages (id, policy_id, code, name, description, limit_amount, limit_note, deductible_amount, tags) VALUES (?,?,?,?,?,?,?,?,?)",
            (_id(), pid, code, name, desc, limit, limit_note, ded, tags))
    for code, text, tags in tpl["exclusions"]:
        conn.execute("INSERT INTO exclusions (id, policy_id, code, text, tags) VALUES (?,?,?,?,?)", (_id(), pid, code, text, tags))
    for code, text, tags in tpl["conditions"]:
        conn.execute("INSERT INTO policy_conditions (id, policy_id, code, text, tags) VALUES (?,?,?,?,?)", (_id(), pid, code, text, tags))
    return pid, aid


INSURER_LINES = {"ins-northstar": ["auto"], "ins-harbourline": ["home"], "ins-brightleaf": ["gadget"]}
TEMPLATES = {"auto": AUTO_POLICY, "home": HOME_POLICY, "gadget": GADGET_POLICY}
ASSET_TYPES = {"auto": "vehicle", "home": "property", "gadget": "device"}


def add_policy_from_template(conn: sqlite3.Connection, holder_id: str, policy_type: str, insurer_id: str, policy_number: str,
                             asset_name: str, asset_details: dict, start_date=None) -> str:
    """User-added policy. Wording is copied from the insurer's sample product (demo: not verified with the insurer)."""
    tpl = dict(TEMPLATES[policy_type])
    tpl["insurer_id"] = insurer_id
    tpl["asset"] = {"asset_type": ASSET_TYPES[policy_type], "name": asset_name,
                    "details": {**asset_details, "Added by": "Policyholder (demo: not verified with insurer)"}}
    start = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc) if start_date else _now()
    pid, _ = _insert_policy(conn, holder_id, tpl, policy_number.upper(), start)
    conn.commit()
    return pid


def add_sample_policies(conn: sqlite3.Connection, holder_id: str, include_gadget: bool = False) -> None:
    """Attach the sample car + home policies to any profile (used for new demo profiles)."""
    suffix = uuid.uuid4().hex[:4].upper()
    start = _now() - timedelta(days=45)
    _insert_policy(conn, holder_id, AUTO_POLICY, f"AUTO-DEMO-{suffix}", start)
    _insert_policy(conn, holder_id, HOME_POLICY, f"HOME-DEMO-{suffix}", start)
    if include_gadget:
        _insert_policy(conn, holder_id, GADGET_POLICY, f"GADG-DEMO-{suffix}", _now() - timedelta(days=10))


def seed(conn: sqlite3.Connection) -> None:
    """Idempotent: only seeds when there are no policyholders."""
    if conn.execute("SELECT COUNT(*) FROM policyholders").fetchone()[0] > 0:
        return
    now = _now()
    conn.executemany("INSERT INTO insurers (id, name, short_name, claims_phone, claims_email, website, address, claims_hours, brand_color) VALUES (?,?,?,?,?,?,?,?,?)", INSURERS)
    conn.executemany("INSERT INTO adjusters (id, insurer_id, full_name, specialization, office_location, phone, email, languages, years_experience, bio) VALUES (?,?,?,?,?,?,?,?,?,?)", ADJUSTERS)
    conn.executemany("INSERT INTO repair_partners (id, insurer_id, name, kind, address, distance_km, rating, phone, services, hours) VALUES (?,?,?,?,?,?,?,?,?,?)", REPAIR_PARTNERS)
    conn.execute("INSERT INTO policyholders (id, full_name, photo_url, city, is_sample, created_at) VALUES (?,?,?,?,?,?)",
                 (DANIEL_ID, "Daniel Reyes", None, "Riverton (fictional)", 1, now.isoformat()))
    conn.execute("INSERT INTO policyholders (id, full_name, photo_url, city, is_sample, created_at) VALUES (?,?,?,?,?,?)",
                 ("ph-priya", "Priya Natarajan", None, "Lakeside (fictional)", 1, now.isoformat()))

    start = now - timedelta(days=45)
    auto_pid, auto_aid = _insert_policy(conn, DANIEL_ID, AUTO_POLICY, "AUTO-DEMO-1001", start)
    _insert_policy(conn, DANIEL_ID, HOME_POLICY, "HOME-DEMO-2001", start)
    _insert_policy(conn, DANIEL_ID, GADGET_POLICY, "GADG-DEMO-3001", now - timedelta(days=10))
    _insert_policy(conn, "ph-priya", HOME_POLICY, "HOME-DEMO-2002", now - timedelta(days=200))

    # Example historical claim scenario for Daniel (fictional).
    cid = "cl-example-glass"
    created = now - timedelta(days=12)
    conn.execute(
        """INSERT INTO claims (id, claim_number, policyholder_id, policy_id, asset_id, category, incident_date, incident_location,
           description, summary, next_steps, documents_to_collect, ai_suggestion, status, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (cid, "CLM-DEMO-0001", DANIEL_ID, auto_pid, auto_aid, "glass", (created - timedelta(days=1)).date().isoformat(),
         "Highway 9 near Riverton exit 14",
         "A stone flew up from a truck on the highway and left a chip about the size of a coin on the windshield, driver side.",
         "Windshield chip (approx. coin size, driver side) caused by road debris on Highway 9.",
         json.dumps(["Book chip repair at a partner glass shop", "Wait for adjuster confirmation of the repair estimate"]),
         json.dumps(["Photo of the chip with a coin for scale"]),
         None, "in_review", created.isoformat(), (created + timedelta(days=1)).isoformat()),
    )
    for i, (status, title, detail, actor, offset) in enumerate([
        ("submitted", "Claim submitted", "Submitted online with 1 photo.", "policyholder", 0),
        ("in_review", "Initial review started", "Claim assigned to the glass claims queue.", "system", 1),
    ]):
        conn.execute("INSERT INTO claim_events (id, claim_id, status, title, detail, actor, created_at) VALUES (?,?,?,?,?,?,?)",
                     (_id(), cid, status, title, detail, actor, (created + timedelta(days=offset, minutes=i)).isoformat()))
    conn.commit()
