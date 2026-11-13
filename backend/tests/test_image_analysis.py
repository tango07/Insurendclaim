"""Image analysis: photos are sent to the vision model and observations are grounded to the images actually sent."""
import json

from conftest import JPG, PNG, make_client, policy_of

DESC = "Someone hit my parked car in the mall car park yesterday and dented the rear bumper."


class VisionFake:
    name = "fake"

    def __init__(self, observations):
        self.observations, self.images = observations, None

    def complete(self, system, user, max_tokens=1500, images=None):
        self.images = images
        return json.dumps({
            "suggested_category": "collision", "category_confidence": "high",
            "incident_summary": "Parked car hit in a car park; photos appear to show a dented rear bumper.",
            "relevant_coverages": [{"coverage_code": "AUTO-COL", "why_relevant": "collision"}], "possible_exclusions": [],
            "missing_information": [], "documents_to_collect": [], "next_steps": ["Get an estimate"], "limitations": [],
            "needs_adjuster_review": False, "image_observations": self.observations})


def _suggest(c, att_ids):
    d = c.get("/api/profiles/ph-daniel").json()
    auto = policy_of(d, "auto")
    return c.post("/api/claims/suggest", json={"policy_id": auto["id"], "asset_id": auto["assets"][0]["id"],
                                                "description": DESC, "attachment_ids": att_ids}).json()


def test_images_sent_and_observations_grounded(tmp_path):
    fake = VisionFake([
        {"filename": "bumper.png", "observation": "Rear bumper appears dented with scuffed paint.", "matches_description": "yes"},
        {"filename": "not-uploaded.jpg", "observation": "Invented", "matches_description": "yes"},
    ])
    with make_client(tmp_path, provider=fake) as c:
        atts = c.post("/api/attachments", files=[("files", ("bumper.png", PNG, "image/png")),
                                                 ("files", ("notes.pdf", b"%PDF-1.4\n", "application/pdf"))]).json()
        g = _suggest(c, [a["id"] for a in atts])
    assert [i["filename"] for i in fake.images] == ["bumper.png"] and fake.images[0]["media_type"] == "image/png"
    assert [o["filename"] for o in g["image_observations"]] == ["bumper.png"]   # invented filename dropped
    assert any("was analysed by AI" in n for n in g["attachment_notes"])
    assert "photos appear to show" in g["incident_summary"]


def test_mismatched_photo_flags_adjuster(tmp_path):
    fake = VisionFake([{"filename": "x.jpg", "observation": "Photo shows a kitchen, not a car.", "matches_description": "no"}])
    with make_client(tmp_path, provider=fake) as c:
        att = c.post("/api/attachments", files=[("files", ("x.jpg", JPG, "image/jpeg"))]).json()
        g = _suggest(c, [att[0]["id"]])
    assert g["needs_adjuster_review"] and any("may not show the insured item" in l for l in g["limitations"])


def test_heic_not_sent_and_explained(tmp_path):
    fake = VisionFake([])
    with make_client(tmp_path, provider=fake) as c:
        att = c.post("/api/attachments", files=[("files", ("phone.heic", b"\x00\x00\x00 ftypheic" + b"\x00" * 50, "image/heic"))]).json()
        g = _suggest(c, [att[0]["id"]])
    assert fake.images is None and any("can't be analysed" in n for n in g["attachment_notes"])


def test_mock_mode_never_claims_analysis(client, daniel):
    att = client.post("/api/attachments", files=[("files", ("bumper.png", PNG, "image/png"))]).json()
    auto = policy_of(daniel, "auto")
    g = client.post("/api/claims/suggest", json={"policy_id": auto["id"], "asset_id": auto["assets"][0]["id"],
                                                  "description": DESC, "attachment_ids": [att[0]["id"]]}).json()
    assert g["image_observations"] == [] and "not analysed" in g["attachment_notes"][0]
