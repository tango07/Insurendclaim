import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai.service import GuidanceService  # noqa: E402
from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PDF = b"%PDF-1.4\n%demo\n"


class AuthedClient(TestClient):
    """TestClient that logs in on enter (default: Daniel's demo account)."""

    username, password = "daniel", "Daniel@123"

    def __enter__(self):
        c = super().__enter__()
        if self.username:
            r = c.post("/api/auth/login", json={"username": self.username, "password": self.password})
            assert r.status_code == 200, r.text
            c.headers["Authorization"] = f"Bearer {r.json()['token']}"
        return c


def make_client(tmp_path, provider=None, login: str | None = "daniel", **overrides) -> TestClient:
    s = Settings(db_path=str(tmp_path / "test.db"), upload_dir=str(tmp_path / "uploads"), llm_provider="mock", **overrides)
    app = create_app(s, GuidanceService(s, provider=provider, use_env_provider=False))
    c = AuthedClient(app)
    c.username = login
    c.password = {"daniel": "Daniel@123", "priya": "Priya@123"}.get(login or "", "")
    return c


@pytest.fixture
def client(tmp_path):
    with make_client(tmp_path) as c:
        yield c


@pytest.fixture
def daniel(client):
    return client.get("/api/profiles/ph-daniel").json()


def policy_of(profile, ptype):
    return next(p for p in profile["policies"] if p["policy_type"] == ptype)
