"""Backend tests for Daniel's core journey and the required edge cases."""
from conftest import JPG, PDF, PNG, make_client, policy_of

from app.ai.providers import ProviderError

COLLISION = "I was rear-ended at a red light on Main Street yesterday evening. The rear bumper is dented and the boot won't close."


def upload(client, files):
    return client.post("/api/attachments", files=[("files", f) for f in files])


# --- Profile & policy -------------------------------------------------------
def test_health_reports_mock_mode(client):
    assert client.get("/api/health").json()["ai_mode"] == "mock"


def test_select_daniel_and_view_linked_policies(client, daniel):
    assert daniel["full_name"] == "Daniel Reyes"
    types = {p["policy_type"] for p in daniel["policies"]}
    assert {"auto", "home"} <= types
    auto = policy_of(daniel, "auto")
    assert auto["assets"][0]["asset_type"] == "vehicle"
    detail = client.get(f"/api/policies/{auto['id']}").json()
    assert detail["coverages"] and detail["exclusions"] and detail["conditions"]
    assert all("deductible_amount" in c and "limit_note" in c for c in detail["coverages"])
    assert "fictional" in detail["insurer_label"].lower()


def test_register_with_and_without_sample_policies(client):
    reg = {"username": "samlee", "password": "Secret@123", "full_name": "  Sam   Lee ", "with_sample_policies": True}
    r = client.post("/api/auth/register", json=reg)
    assert r.status_code == 201 and r.json()["profile"]["full_name"] == "Sam Lee" and len(r.json()["profile"]["policies"]) == 2
    r = client.post("/api/auth/register", json=reg | {"username": "empty1", "with_sample_policies": False})
    assert r.status_code == 201 and r.json()["profile"]["policies"] == []
    assert client.post("/api/auth/register", json=reg | {"username": "x1", "full_name": "x"}).status_code == 422


def test_other_profile_forbidden(client):
    assert client.get("/api/profiles/ph-priya").status_code == 403


# --- Attachments -------------------------------------------------------------
def test_multiple_valid_attachments(client):
    r = upload(client, [("bumper.png", PNG, "image/png"), ("scene.jpg", JPG, "image/jpeg"), ("estimate.pdf", PDF, "application/pdf")])
    assert r.status_code == 201
    assert [a["original_filename"] for a in r.json()] == ["bumper.png", "scene.jpg", "estimate.pdf"]


def test_invalid_file_type_rejected(client):
    r = upload(client, [("virus.exe", b"MZ....", "application/octet-stream")])
    assert r.status_code == 400 and "not allowed" in r.json()["detail"]


def test_mismatched_content_rejected(client):
    r = upload(client, [("fake.png", b"not really a png", "image/png")])
    assert r.status_code == 400 and "does not match" in r.json()["detail"]


def test_oversized_file_rejected(tmp_path):
    with make_client(tmp_path, max_upload_mb=0.001) as c:  # ~1 KB
        r = upload(c, [("big.png", PNG + b"\x00" * 5000, "image/png")])
        assert r.status_code == 400 and "limit" in r.json()["detail"]


# --- AI suggestion -----------------------------------------------------------
def suggest(client, policy, description=COLLISION, attachment_ids=(), **extra):
    return client.post("/api/claims/suggest", json={"policy_id": policy["id"], "asset_id": policy["assets"][0]["id"],
                                                    "description": description, "attachment_ids": list(attachment_ids), **extra})


def test_mock_suggestion_has_all_fields_and_is_grounded(client, daniel):
    auto = policy_of(daniel, "auto")
    att = upload(client, [("bumper.png", PNG, "image/png")]).json()
    r = suggest(client, auto, attachment_ids=[att[0]["id"]])
    assert r.status_code == 200
    g = r.json()
    for k in ["suggested_category", "incident_summary", "relevant_coverages", "missing_information", "next_steps",
              "documents_to_collect", "limitations", "attachment_notes", "disclaimer", "provider"]:
        assert k in g
    assert g["suggested_category"] == "collision" and g["provider"] == "mock"
    codes = {c["code"] for c in client.get(f"/api/policies/{auto['id']}").json()["coverages"]}
    assert g["relevant_coverages"] and all(c["coverage_code"] in codes for c in g["relevant_coverages"])
    assert "AUTO-COL" in {c["coverage_code"] for c in g["relevant_coverages"]}
    assert "not analysed" in g["attachment_notes"][0]  # no fake image analysis
    assert "not a coverage decision" in g["disclaimer"]


def test_home_water_leak(client, daniel):
    g = suggest(client, policy_of(daniel, "home"),
                "Water is dripping through the kitchen ceiling from the apartment upstairs, a pipe burst this morning.").json()
    assert g["suggested_category"] == "water"
    assert "HOME-WATER" in {c["coverage_code"] for c in g["relevant_coverages"]}
    assert "HOME-EX-GRAD" in {e["code"] for e in g["possible_exclusions"]}


def test_missing_policy_context_gives_limitation_not_invented_terms(client, daniel):
    gadget = policy_of(daniel, "gadget")
    g = suggest(client, gadget, "I dropped my laptop on the floor at home and the screen cracked badly.").json()
    assert g["relevant_coverages"] == [] and g["possible_exclusions"] == []
    assert g["needs_adjuster_review"] is True
    assert any("not available" in lim for lim in g["limitations"])


def test_asset_must_belong_to_policy(client, daniel):
    auto, home = policy_of(daniel, "auto"), policy_of(daniel, "home")
    r = client.post("/api/claims/suggest", json={"policy_id": auto["id"], "asset_id": home["assets"][0]["id"], "description": COLLISION})
    assert r.status_code == 400


def test_description_too_short(client, daniel):
    r = suggest(client, policy_of(daniel, "auto"), "crash")
    assert r.status_code == 422 and "description" in r.json()["detail"]


# --- Provider failure modes --------------------------------------------------
class FakeProvider:
    name = "fake"

    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []

    def complete(self, system, user, max_tokens=1500, images=None):
        self.calls.append(user)
        if self.error:
            raise self.error
        return self.reply


def test_provider_error_falls_back_to_mock(tmp_path):
    with make_client(tmp_path, provider=FakeProvider(error=ProviderError("AI provider timed out after 25s"))) as c:
        d = c.get("/api/profiles/ph-daniel").json()
        g = suggest(c, policy_of(d, "auto")).json()
        assert g["provider"] == "mock" and "timed out" in g["fallback_reason"]


def test_invalid_model_output_falls_back(tmp_path):
    with make_client(tmp_path, provider=FakeProvider(reply='{"oops": true}')) as c:
        d = c.get("/api/profiles/ph-daniel").json()
        g = suggest(c, policy_of(d, "auto")).json()
        assert g["provider"] == "mock" and "expected structure" in g["fallback_reason"]


def test_invented_coverage_codes_are_removed_and_pii_not_sent(tmp_path):
    reply = """```json
    {"suggested_category": "collision", "category_confidence": "high", "incident_summary": "Rear-end collision at a red light.",
     "relevant_coverages": [{"coverage_code": "AUTO-COL", "why_relevant": "collision"}, {"coverage_code": "MADE-UP", "why_relevant": "x"}],
     "possible_exclusions": [], "missing_information": [], "documents_to_collect": [], "next_steps": ["Get an estimate"],
     "limitations": [], "needs_adjuster_review": false}
    ```"""
    fp = FakeProvider(reply=reply)
    with make_client(tmp_path, provider=fp) as c:
        d = c.get("/api/profiles/ph-daniel").json()
        g = suggest(c, policy_of(d, "auto")).json()
        assert g["provider"] == "fake"
        assert [x["coverage_code"] for x in g["relevant_coverages"]] == ["AUTO-COL"]
        assert g["relevant_coverages"][0]["deductible_amount"] == 500  # enriched from DB, not model
        assert any("removed" in lim for lim in g["limitations"])
        assert "Daniel" not in fp.calls[0] and "HOME-" not in fp.calls[0]  # no name, no unrelated policy


# --- Submission & status -----------------------------------------------------
def test_edit_and_submit_claim_then_view_status(client, daniel):
    auto = policy_of(daniel, "auto")
    atts = upload(client, [("a.png", PNG, "image/png"), ("b.jpg", JPG, "image/jpeg")]).json()
    g = suggest(client, auto, attachment_ids=[a["id"] for a in atts]).json()
    body = {"policyholder_id": "ph-daniel", "policy_id": auto["id"], "asset_id": auto["assets"][0]["id"],
            "description": COLLISION, "attachment_ids": [a["id"] for a in atts],
            "category": "collision", "summary": "EDITED: rear-end collision on Main Street, bumper dented.",
            "next_steps": g["next_steps"][:2] + ["My own step"], "documents_to_collect": ["Photos"], "ai_suggestion": g,
            "incident_location": "Main Street"}
    r = client.post("/api/claims", json=body)
    assert r.status_code == 201, r.text
    claim = r.json()
    assert claim["status"] == "submitted" and claim["summary"].startswith("EDITED")
    assert "My own step" in claim["next_steps"] and len(claim["attachments"]) == 2
    assert claim["events"][0]["title"] == "Claim submitted" and claim["upcoming"]
    assert claim["ai_suggestion"]["suggested_category"] == "collision"
    listed = client.get("/api/profiles/ph-daniel/claims").json()
    assert claim["id"] in [c["id"] for c in listed]
    # attachments cannot be reused on another claim
    assert client.post("/api/claims", json=body).status_code == 400


def test_cannot_submit_against_someone_elses_policy(client, daniel):
    auto = policy_of(daniel, "auto")
    body = {"policyholder_id": "ph-priya", "policy_id": auto["id"], "asset_id": auto["assets"][0]["id"],
            "description": COLLISION, "category": "collision", "summary": "Rear-end collision."}
    assert client.post("/api/claims", json=body).status_code == 403


def test_seeded_example_claim_visible(client):
    claims = client.get("/api/profiles/ph-daniel/claims").json()
    assert any(c["claim_number"] == "CLM-DEMO-0001" and c["status"] == "in_review" for c in claims)


# --- Assistant ---------------------------------------------------------------
def test_assistant_answers_from_policy(client, daniel):
    auto = policy_of(daniel, "auto")
    a = client.post("/api/assistant", json={"policy_id": auto["id"], "question": "What is my deductible?"}).json()
    assert "$500" in a["answer"] and a["provider"] == "mock"
    a = client.post("/api/assistant", json={"policy_id": policy_of(daniel, "home")["id"], "question": "Is flood covered?"}).json()
    assert "HOME-EX-FLOOD" in a["sources"]
    gadget = policy_of(daniel, "gadget")
    a = client.post("/api/assistant", json={"policy_id": gadget["id"], "question": "Is my screen covered?"}).json()
    assert "adjuster" in a["answer"]
