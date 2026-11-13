"""All SQL lives here. Functions take a DB-API connection and return plain dicts."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from . import seed as seed_mod


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row(r: Optional[sqlite3.Row]) -> Optional[dict]:
    return dict(r) if r is not None else None


# ---------- Profiles ----------
def list_profiles(conn) -> list[dict]:
    rows = conn.execute(
        """SELECT p.*, (SELECT COUNT(*) FROM policies x WHERE x.policyholder_id = p.id) AS policy_count
           FROM policyholders p ORDER BY p.is_sample DESC, p.created_at"""
    ).fetchall()
    return [dict(r) | {"is_sample": bool(r["is_sample"])} for r in rows]


def get_profile(conn, profile_id: str) -> Optional[dict]:
    r = conn.execute(
        """SELECT p.*, (SELECT COUNT(*) FROM policies x WHERE x.policyholder_id = p.id) AS policy_count
           FROM policyholders p WHERE p.id = ?""", (profile_id,)).fetchone()
    if not r:
        return None
    d = dict(r) | {"is_sample": bool(r["is_sample"])}
    d["policies"] = list_policies(conn, profile_id)
    return d


def create_profile(conn, full_name: str, city: Optional[str], with_sample_policies: bool, commit: bool = True) -> dict:
    pid = f"ph-{uuid.uuid4().hex[:10]}"
    conn.execute("INSERT INTO policyholders (id, full_name, photo_url, city, is_sample, created_at) VALUES (?,?,?,?,?,?)",
                 (pid, full_name, None, city, 0, _now()))
    if with_sample_policies:
        seed_mod.add_sample_policies(conn, pid)
    if commit:
        conn.commit()
    return get_profile(conn, pid)


def list_insurers(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM insurers ORDER BY name")]


def policy_number_exists(conn, number: str) -> bool:
    return conn.execute("SELECT 1 FROM policies WHERE UPPER(policy_number) = UPPER(?)", (number,)).fetchone() is not None


# ---------- Policies ----------
def _assets_for(conn, policy_id: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM insured_assets WHERE policy_id = ?", (policy_id,)).fetchall()
    return [dict(r) | {"details": json.loads(r["details"] or "{}")} for r in rows]


def get_insurer(conn, insurer_id: str) -> Optional[dict]:
    return _row(conn.execute("SELECT * FROM insurers WHERE id = ?", (insurer_id,)).fetchone())


def _policy_base(conn, r: sqlite3.Row) -> dict:
    return dict(r) | {"wording_available": bool(r["wording_available"]), "assets": _assets_for(conn, r["id"]),
                      "insurer": get_insurer(conn, r["insurer_id"])}


def list_policies(conn, profile_id: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM policies WHERE policyholder_id = ? ORDER BY policy_type", (profile_id,)).fetchall()
    return [_policy_base(conn, r) for r in rows]


def get_policy(conn, policy_id: str) -> Optional[dict]:
    r = conn.execute("SELECT * FROM policies WHERE id = ?", (policy_id,)).fetchone()
    if not r:
        return None
    d = _policy_base(conn, r)
    d["insurer_label"] = f"{d['insurer']['name']}: sample data only, not a real insurer"
    d["coverages"] = [dict(x) for x in conn.execute("SELECT * FROM coverages WHERE policy_id = ? ORDER BY rowid", (policy_id,))]
    d["exclusions"] = [dict(x) for x in conn.execute("SELECT * FROM exclusions WHERE policy_id = ? ORDER BY rowid", (policy_id,))]
    d["conditions"] = [dict(x) for x in conn.execute("SELECT * FROM policy_conditions WHERE policy_id = ? ORDER BY rowid", (policy_id,))]
    return d


def get_asset(conn, asset_id: str) -> Optional[dict]:
    r = conn.execute("SELECT * FROM insured_assets WHERE id = ?", (asset_id,)).fetchone()
    return dict(r) | {"details": json.loads(r["details"] or "{}")} if r else None


# ---------- Attachments ----------
def create_attachment(conn, filename: str, content_type: str, size: int, storage_key: str, owner_id: str) -> dict:
    aid = f"att-{uuid.uuid4().hex[:12]}"
    conn.execute("INSERT INTO claim_attachments (id, claim_id, owner_id, original_filename, content_type, size_bytes, storage_key, uploaded_at) VALUES (?,?,?,?,?,?,?,?)",
                 (aid, None, owner_id, filename, content_type, size, storage_key, _now()))
    conn.commit()
    return get_attachment(conn, aid)


def get_attachment(conn, attachment_id: str) -> Optional[dict]:
    return _row(conn.execute("SELECT * FROM claim_attachments WHERE id = ?", (attachment_id,)).fetchone())


def get_attachments(conn, ids: list[str]) -> list[dict]:
    out = []
    for i in ids:
        a = get_attachment(conn, i)
        if a:
            out.append(a)
    return out


# ---------- Claims ----------
def _next_claim_number(conn) -> str:
    n = conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0] + 1
    return f"CLM-DEMO-{n:04d}-{uuid.uuid4().hex[:3].upper()}"


def add_event(conn, claim_id: str, status: str, title: str, detail: Optional[str], actor: str) -> None:
    conn.execute("INSERT INTO claim_events (id, claim_id, status, title, detail, actor, created_at) VALUES (?,?,?,?,?,?,?)",
                 (str(uuid.uuid4()), claim_id, status, title, detail, actor, _now()))


def create_claim(conn, data: dict) -> str:
    cid = f"cl-{uuid.uuid4().hex[:12]}"
    now = _now()
    conn.execute(
        """INSERT INTO claims (id, claim_number, policyholder_id, policy_id, asset_id, category, incident_date, incident_location,
           description, summary, next_steps, documents_to_collect, ai_suggestion, status, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (cid, _next_claim_number(conn), data["policyholder_id"], data["policy_id"], data["asset_id"], data["category"],
         data.get("incident_date"), data.get("incident_location"), data["description"], data["summary"],
         json.dumps(data.get("next_steps", [])), json.dumps(data.get("documents_to_collect", [])),
         json.dumps(data["ai_suggestion"]) if data.get("ai_suggestion") else None, "submitted", now, now))
    for att_id in data.get("attachment_ids", []):
        conn.execute("UPDATE claim_attachments SET claim_id = ? WHERE id = ? AND claim_id IS NULL", (cid, att_id))
    n_att = len(data.get("attachment_ids", []))
    add_event(conn, cid, "submitted", "Claim submitted",
              f"Submitted online with {n_att} attachment{'s' if n_att != 1 else ''}.", "policyholder")
    add_event(conn, cid, "submitted", "Acknowledgement sent",
              "Automatic acknowledgement. A claims handler will review the details.", "system")
    conn.commit()
    return cid


def _claim_row_to_dict(conn, r: sqlite3.Row) -> dict:
    d = dict(r)
    d["next_steps"] = json.loads(d["next_steps"] or "[]")
    d["documents_to_collect"] = json.loads(d["documents_to_collect"] or "[]")
    d["ai_suggestion"] = json.loads(d["ai_suggestion"]) if d.get("ai_suggestion") else None
    d["attachments"] = [dict(a) for a in conn.execute(
        "SELECT * FROM claim_attachments WHERE claim_id = ? ORDER BY uploaded_at", (d["id"],))]
    d["events"] = [dict(e) for e in conn.execute(
        "SELECT * FROM claim_events WHERE claim_id = ? ORDER BY created_at", (d["id"],))]
    d["appointments"] = _appointments_where(conn, "ap.claim_id = ?", (d["id"],))
    return d


def _appointments_where(conn, where: str, args: tuple) -> list[dict]:
    rows = conn.execute(
        f"""SELECT ap.*, ad.full_name AS adjuster_name, ad.phone AS adjuster_phone, ad.email AS adjuster_email,
                   ad.office_location AS adjuster_office, ad.specialization AS adjuster_specialization
            FROM appointments ap JOIN adjusters ad ON ad.id = ap.adjuster_id WHERE {where} ORDER BY ap.slot_start""", args).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["instructions"] = json.loads(d["instructions"] or "[]")
        ids = json.loads(d["shared_attachment_ids"] or "[]")
        d["shared_attachments"] = [a["original_filename"] for a in get_attachments(conn, ids)]
        out.append(d)
    return out


_CLAIM_SELECT ="""SELECT c.*, p.policy_number, p.policy_type, a.name AS asset_name
                   FROM claims c JOIN policies p ON p.id = c.policy_id JOIN insured_assets a ON a.id = c.asset_id"""


def get_claim(conn, claim_id: str) -> Optional[dict]:
    r = conn.execute(_CLAIM_SELECT + " WHERE c.id = ?", (claim_id,)).fetchone()
    return _claim_row_to_dict(conn, r) if r else None


def list_claims(conn, profile_id: str) -> list[dict]:
    rows = conn.execute(_CLAIM_SELECT + " WHERE c.policyholder_id = ? ORDER BY c.created_at DESC", (profile_id,)).fetchall()
    return [_claim_row_to_dict(conn, r) for r in rows]


# ---------- Adjusters, repair partners, appointments ----------
SPECIALIZATION_FOR = {"auto": "motor", "home": "property", "gadget": "devices"}


def list_adjusters(conn, insurer_id: str, specialization: Optional[str]) -> list[dict]:
    q, args = "SELECT * FROM adjusters WHERE insurer_id = ?", [insurer_id]
    if specialization:
        q += " AND specialization = ?"
        args.append(specialization)
    return [dict(r) for r in conn.execute(q + " ORDER BY years_experience DESC", args)]


def get_adjuster(conn, adjuster_id: str) -> Optional[dict]:
    return _row(conn.execute("SELECT * FROM adjusters WHERE id = ?", (adjuster_id,)).fetchone())


def booked_slots(conn, adjuster_id: str) -> set[str]:
    return {r[0] for r in conn.execute("SELECT slot_start FROM appointments WHERE adjuster_id = ? AND status = 'confirmed'", (adjuster_id,))}


def list_repair_partners(conn, insurer_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM repair_partners WHERE insurer_id = ? ORDER BY distance_km", (insurer_id,))]


def create_appointment(conn, data: dict) -> str:
    aid = f"ap-{uuid.uuid4().hex[:10]}"
    ref = f"APT-{uuid.uuid4().hex[:6].upper()}"
    conn.execute(
        """INSERT INTO appointments (id, reference, adjuster_id, policyholder_id, policy_id, claim_id, slot_start, duration_minutes, mode,
           contact_name, contact_phone, meeting_location, meeting_link, instructions, directions, shared_attachment_ids, status, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (aid, ref, data["adjuster_id"], data["policyholder_id"], data["policy_id"], data.get("claim_id"), data["slot_start"],
         data["duration_minutes"], data["mode"], data["contact_name"], data["contact_phone"], data.get("meeting_location"),
         data.get("meeting_link"), json.dumps(data["instructions"]), data.get("directions"),
         json.dumps(data.get("shared_attachment_ids", [])), "confirmed", _now()))
    if data.get("claim_id"):
        add_event(conn, data["claim_id"], "in_review", "Adjuster appointment booked",
                  f"{data['adjuster_name']}, {data['slot_label']} ({data['mode_label']}). Reference {ref}.", "policyholder")
        conn.execute("UPDATE claims SET status = 'in_review', updated_at = ? WHERE id = ? AND status = 'submitted'", (_now(), data["claim_id"]))
    conn.commit()
    return aid


def get_appointment(conn, appointment_id: str) -> Optional[dict]:
    rows = _appointments_where(conn, "ap.id = ?", (appointment_id,))
    return rows[0] if rows else None


def list_appointments(conn, profile_id: str) -> list[dict]:
    return _appointments_where(conn, "ap.policyholder_id = ?", (profile_id,))
