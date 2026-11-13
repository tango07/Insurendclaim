"""Database access. SQLite for the MVP; all SQL lives in repositories.py so a
PostgreSQL adapter only needs to replace `connect()` and the `?` placeholders."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterator

from .config import get_settings

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or get_settings().db_path
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


_ALL_TABLES = ["sessions", "users", "appointments", "claim_events", "claim_attachments", "claims", "policy_conditions", "exclusions",
               "coverages", "insured_assets", "policies", "policyholders", "repair_partners", "adjusters", "insurers"]


def init_db(conn: sqlite3.Connection) -> None:
    # Demo-only "migration": if a DB from an older version (no insurers) exists, rebuild it from seed data.
    cols = {r[1] for r in conn.execute("PRAGMA table_info(policies)")}
    att_cols = {r[1] for r in conn.execute("PRAGMA table_info(claim_attachments)")}
    if (cols and "insurer_id" not in cols) or (att_cols and "owner_id" not in att_cols):
        conn.execute("PRAGMA foreign_keys = OFF")
        for t in _ALL_TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {t}")
        conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()


def get_conn() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
