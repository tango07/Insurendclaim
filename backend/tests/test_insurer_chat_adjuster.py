"""Insurer details, chat intent/follow-ups, and the 'speak with an adjuster' journey (slide: User Journey steps 1-7)."""
from conftest import PNG, make_client, policy_of

from app.ai.providers import ProviderError

PARKING = "My car was hit in a parking lot. How do I claim, and which garage nearby can repair it?"


def test_policies_carry_insurer_details(client, daniel):
    auto, home = policy_of(daniel, "auto"), policy_of(daniel, "home")
    assert auto["insurer"]["short_name"] == "Northstar" and home["insurer"]["short_name"] == "Harbourline"
    assert "fictional" in auto["insurer"]["name"] and auto["insurer"]["claims_phone"]
    assert "Northstar" in client.get(f"/api/policies/{auto['id']}").json()["insurer_label"]


def test_intent_for_slide_step_2(client, daniel):
    r = client.post("/api/chat/intent", json={"policy_id": policy_of(daniel, "auto")["id"], "message": PARKING}).json()
    ids = [a["id"] for a in r["actions"]]
    assert ids[:2] == ["start_claim", "speak_adjuster"] and "find_garage" in ids
    assert r["looks_like_incident"] is True and "Northstar" in r["reply"]


def test_intent_question_routes_to_assistant(client, daniel):
    r = client.post("/api/chat/intent", json={"policy_id": policy_of(daniel, "auto")["id"], "message": "What is my deductible?"}).json()
    assert r["intents"] == ["question"] and r["actions"] == []


def follow(client, policy, description, asked):
    return client.post("/api/claims/follow-up", json={"policy_id": policy["id"], "asset_id": policy["assets"][0]["id"],
                                                      "description": description, "asked_keys": asked}).json()


def test_follow_up_questions_progress_and_stop(client, daniel):
    auto = policy_of(daniel, "auto")
    asked, desc = [], PARKING
    for _ in range(6):
        q = follow(client, auto, desc, asked)
        if q["done"]:
            break
        assert q["key"] not in asked and "?" in q["question"]
        asked.append(q["key"])
        desc += f"\n- {q['question']}: answer"
    assert q["done"] is True and 1 <= len(asked) <= 5
    assert "when" in asked  # no date in the original message


def test_answered_keys_remove_missing_info(client, daniel):
    auto = policy_of(daniel, "auto")
    base = {"policy_id": auto["id"], "asset_id": auto["assets"][0]["id"], "description": PARKING}
    before = client.post("/api/claims/suggest", json=base).json()["missing_information"]
    after = client.post("/api/claims/suggest", json=base | {"answered_keys": ["when", "other_party", "injuries"]}).json()["missing_information"]
    assert len(after) < len(before) and not any("Date" in m for m in after)


class Phraser:
    name = "fake"

    def __init__(self, reply=None, error=None):
        self.reply, self.error = reply, error

    def complete(self, system, user, max_tokens=1500, images=None):
        if self.error:
            raise self.error
        return self.reply


def test_follow_up_llm_phrasing_constrained_to_known_gaps(tmp_path):
    with make_client(tmp_path, provider=Phraser('{"done": false, "key": "invented", "question": "What is your bank account?"}')) as c:
        d = c.get("/api/profiles/ph-daniel").json()
        q = follow(c, policy_of(d, "auto"), PARKING, [])
        assert q["provider"] == "mock" and q["key"] != "invented"  # rejected, fell back to rules
    with make_client(tmp_path / "b", provider=Phraser('{"done": false, "key": "when", "question": "Oh no! Roughly when did it happen?"}')) as c:
        d = c.get("/api/profiles/ph-daniel").json()
        q = follow(c, policy_of(d, "auto"), PARKING, [])
        assert q == {"done": False, "key": "when", "question": "Oh no! Roughly when did it happen?", "why": q["why"], "provider": "fake"}
    with make_client(tmp_path / "c", provider=Phraser(error=ProviderError("timeout"))) as c:
        d = c.get("/api/profiles/ph-daniel").json()
        assert follow(c, policy_of(d, "auto"), PARKING, [])["provider"] == "mock"


# --- Adjuster journey (slide steps 3-7) ---------------------------------------
def test_adjusters_match_insurer_and_specialization(client, daniel):
    adj = client.get(f"/api/policies/{policy_of(daniel, 'auto')['id']}/adjusters").json()
    assert len(adj) == 3 and all(a["specialization"] == "motor" and "Northstar" in a["insurer_name"] for a in adj)
    assert all(a["slots"] and a["office_location"] for a in adj)
    remote = next(a for a in adj if a["office_location"].startswith("Remote"))
    assert "onsite" not in remote["allowed_modes"]
    home_adj = client.get(f"/api/policies/{policy_of(daniel, 'home')['id']}/adjusters").json()
    assert {a["specialization"] for a in home_adj} == {"property"}


def test_garages_for_insurer(client, daniel):
    g = client.get(f"/api/policies/{policy_of(daniel, 'auto')['id']}/repair-partners").json()
    assert g and g[0]["distance_km"] <= g[-1]["distance_km"] and {x["kind"] for x in g} <= {"garage", "glass"}


def book_body(daniel, adj, slot, **kw):
    auto = policy_of(daniel, "auto")
    return {"adjuster_id": adj["id"], "policyholder_id": "ph-daniel", "policy_id": auto["id"], "slot_start": slot,
            "mode": "onsite", "contact_name": "Daniel Reyes", "contact_phone": "+1 555 0199 123",
            "meeting_location": "Riverside Mall car park, level 2"} | kw


def test_book_onsite_inspection_full_journey(client, daniel):
    auto = policy_of(daniel, "auto")
    adj = [a for a in client.get(f"/api/policies/{auto['id']}/adjusters").json() if "onsite" in a["allowed_modes"]][0]
    att = client.post("/api/attachments", files=[("files", ("dent.png", PNG, "image/png"))]).json()
    slot = adj["slots"][0]
    r = client.post("/api/appointments", json=book_body(daniel, adj, slot, attachment_ids=[att[0]["id"]]))
    assert r.status_code == 201, r.text
    ap = r.json()
    assert ap["reference"].startswith("APT-") and ap["adjuster_name"] == adj["full_name"]
    assert ap["directions"] and "Riverside Mall" in ap["directions"]
    assert any("photos" in i.lower() for i in ap["instructions"]) and ap["shared_attachments"] == ["dent.png"]
    # slot no longer offered, and double booking rejected
    again = client.get(f"/api/policies/{auto['id']}/adjusters").json()
    assert slot not in next(a for a in again if a["id"] == adj["id"])["slots"]
    assert client.post("/api/appointments", json=book_body(daniel, adj, slot)).status_code == 409
    assert len(client.get("/api/profiles/ph-daniel/appointments").json()) == 1


def test_video_link_and_claim_timeline(client, daniel):
    auto = policy_of(daniel, "auto")
    adj = client.get(f"/api/policies/{auto['id']}/adjusters").json()[0]
    ap = client.post("/api/appointments", json=book_body(daniel, adj, adj["slots"][1], mode="video", meeting_location=None,
                                                         claim_id="cl-example-glass")).json()
    assert ap["meeting_link"].startswith("https://teams.example.invalid/")
    claim = client.get("/api/claims/cl-example-glass").json()
    assert claim["appointments"][0]["reference"] == ap["reference"]
    assert claim["events"][-1]["title"] == "Adjuster appointment booked"


def test_booking_validation(client, daniel):
    auto = policy_of(daniel, "auto")
    adjs = client.get(f"/api/policies/{auto['id']}/adjusters").json()
    adj = adjs[0]
    remote = next(a for a in adjs if a["office_location"].startswith("Remote"))
    assert client.post("/api/appointments", json=book_body(daniel, adj, adj["slots"][0], contact_phone="abc")).status_code == 422
    assert client.post("/api/appointments", json=book_body(daniel, adj, "2020-01-01T09:30")).status_code == 409
    assert client.post("/api/appointments", json=book_body(daniel, adj, adj["slots"][0], meeting_location="")).status_code == 400
    assert client.post("/api/appointments", json=book_body(daniel, remote, remote["slots"][0])).status_code == 400
    home_adj = client.get(f"/api/policies/{policy_of(daniel, 'home')['id']}/adjusters").json()[0]
    assert client.post("/api/appointments", json=book_body(daniel, home_adj, home_adj["slots"][0])).status_code == 400
