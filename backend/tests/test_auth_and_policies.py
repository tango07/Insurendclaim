"""Login, access control, add-a-policy, and adjuster directory."""
from conftest import make_client, policy_of

from app import auth


def test_password_hashing():
    digest, salt = auth.hash_password("Daniel@123")
    assert digest != "Daniel@123" and auth.verify_password("Daniel@123", digest, salt) and not auth.verify_password("wrong", digest, salt)


def test_login_logout_and_me(tmp_path):
    with make_client(tmp_path, login=None) as c:
        assert c.get("/api/profiles/ph-daniel").status_code == 401           # no token
        assert c.post("/api/auth/login", json={"username": "daniel", "password": "nope"}).status_code == 401
        r = c.post("/api/auth/login", json={"username": "DANIEL", "password": "Daniel@123"})  # username case-insensitive
        assert r.status_code == 200 and r.json()["profile"]["full_name"] == "Daniel Reyes"
        h = {"Authorization": f"Bearer {r.json()['token']}"}
        assert c.get("/api/auth/me", headers=h).json()["username"] == "daniel"
        assert c.post("/api/auth/logout", headers=h).status_code == 204
        assert c.get("/api/auth/me", headers=h).status_code == 401             # token revoked
        # password not stored in clear text
        import sqlite3
        row = sqlite3.connect(str(tmp_path / "test.db")).execute("SELECT password_hash FROM users WHERE username='daniel'").fetchone()
        assert row and "Daniel@123" not in row[0]


def test_register_rules(client):
    base = {"username": "newuser", "full_name": "New User"}
    for bad in ["abcdef", "123456", "@@@@", "abc123", "abc@", "12@"]:          # each misses letter, number or symbol
        assert client.post("/api/auth/register", json=base | {"password": bad}).status_code == 400, bad
    assert client.post("/api/auth/register", json=base | {"username": "daniel", "password": "a1@"}).status_code == 409
    for bad_u in ["ab", "akshay kumar", "akshay#1"]:
        r = client.post("/api/auth/register", json=base | {"username": bad_u, "password": "a1@"})
        assert r.status_code == 400 and "Username" in r.json()["detail"], bad_u
    r = client.post("/api/auth/register", json=base | {"username": "akshay.kumar@epam.example", "password": "a1@"})
    assert r.status_code == 201
    assert client.post("/api/auth/login", json={"username": "Akshay.Kumar@epam.example", "password": "a1@"}).status_code == 200
    r = client.post("/api/auth/register", json=base | {"password": "a1@"})    # letter + number + symbol is enough
    assert r.status_code == 201 and r.json()["token"]


def test_cannot_see_other_users_policy(tmp_path, daniel):
    with make_client(tmp_path / "p", login="priya") as c:
        d = c.get("/api/profiles/ph-priya").json()
        assert c.get("/api/profiles/ph-daniel").status_code == 403
        assert len(d["policies"]) == 1
    with make_client(tmp_path / "d") as c:
        dan_auto = policy_of(c.get("/api/profiles/ph-daniel").json(), "auto")
    with make_client(tmp_path / "d", login="priya") as c:   # same DB, logged in as Priya
        assert c.get(f"/api/policies/{dan_auto['id']}").status_code == 404
        assert c.get(f"/api/policies/{dan_auto['id']}/adjusters").status_code == 404


def test_add_second_car_policy_and_claim_on_it(client):
    ins = client.get("/api/insurers").json()
    assert {"ins-northstar": ["auto"]}.items() <= {i["id"]: i["lines"] for i in ins}.items()
    body = {"policy_type": "auto", "insurer_id": "ins-northstar", "policy_number": "nsm-778812",
            "asset_name": "2019 Honda Jazz", "asset_details": {"Registration": "DEMO-7788", "Colour": "Blue"}}
    r = client.post("/api/me/policies", json=body)
    assert r.status_code == 201, r.text
    cars = [p for p in r.json()["policies"] if p["policy_type"] == "auto"]
    new = next(p for p in cars if p["policy_number"] == "NSM-778812")
    assert len(cars) == 2 and new["assets"][0]["name"] == "2019 Honda Jazz" and new["insurer"]["short_name"] == "Northstar"
    assert new["assets"][0]["details"]["Registration"] == "DEMO-7788"
    # same number again -> conflict; wrong insurer line -> 400; bad number -> 422
    assert client.post("/api/me/policies", json=body).status_code == 409
    assert client.post("/api/me/policies", json=body | {"policy_number": "NSM-000001", "insurer_id": "ins-harbourline"}).status_code == 400
    assert client.post("/api/me/policies", json=body | {"policy_number": "a b"}).status_code == 422
    # the new policy is fully usable: coverage, guidance, adjusters
    detail = client.get(f"/api/policies/{new['id']}").json()
    assert detail["coverages"] and detail["exclusions"]
    g = client.post("/api/claims/suggest", json={"policy_id": new["id"], "asset_id": new["assets"][0]["id"],
                                                  "description": "Someone reversed into my Jazz in the office car park and dented the door."}).json()
    assert g["suggested_category"] == "collision" and g["relevant_coverages"]
    assert len(client.get(f"/api/policies/{new['id']}/adjusters").json()) == 3


def test_adjuster_directory_and_assistant(client, daniel):
    d = client.get("/api/me/adjusters").json()
    names = {a["full_name"] for a in d}
    assert {"Maya Okafor", "Samir Haddad", "Ola Nilsen"} <= names and all(a["phone"] and a["office_location"] for a in d)
    auto = policy_of(daniel, "auto")
    a = client.post("/api/assistant", json={"policy_id": auto["id"], "question": "Who is my adjuster?"}).json()
    assert a["provider"] == "directory" and "Maya Okafor" in a["answer"] and "+1 555" in a["answer"]


def test_typed_adjuster_request_goes_straight_to_list(client, daniel):
    r = client.post("/api/chat/intent", json={"policy_id": policy_of(daniel, "auto")["id"], "message": "Show me adjuster details"}).json()
    assert r["auto_action"] == "speak_adjuster"
