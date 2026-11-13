"""Username/password login with opaque session tokens. Standard library only.

- Passwords: PBKDF2-HMAC-SHA256, 200k iterations, 16-byte random salt per user.
- Sessions: random 32-byte token returned once; only its SHA-256 is stored. 12h expiry.
Swap for OIDC/SSO in production.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

ITERATIONS = 200_000
SESSION_HOURS = 12
USERNAME_RE = re.compile(r"^[A-Za-z0-9._@+-]{3,50}$")  # plain names or email addresses


def username_problem(username: str) -> Optional[str]:
    u = username.strip()
    if len(u) < 3:
        return "Username must be at least 3 characters."
    if len(u) > 50:
        return "Username must be 50 characters or fewer."
    if " " in u:
        return "Username can't contain spaces. Try e.g. akshay.kumar."
    bad = sorted({ch for ch in u if not re.match(r"[A-Za-z0-9._@+-]", ch)})
    if bad:
        return f"Username can't contain: {' '.join(bad)}. Use letters, numbers, . _ - @ or +."
    return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return digest, salt


def verify_password(password: str, digest: str, salt: str) -> bool:
    return hmac.compare_digest(hash_password(password, salt)[0], digest)


def password_problem(password: str) -> Optional[str]:
    """Rule: at least one letter, one number and one special symbol. Nothing else."""
    if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password) and re.search(r"[^A-Za-z0-9\s]", password)):
        return "Password must contain at least one letter, one number and one special symbol (e.g. @ # $ !)."
    return None


def create_user(conn, username: str, password: str, policyholder_id: str) -> str:
    uid = f"u-{uuid.uuid4().hex[:10]}"
    digest, salt = hash_password(password)
    conn.execute("INSERT INTO users (id, username, password_hash, password_salt, policyholder_id, created_at) VALUES (?,?,?,?,?,?)",
                 (uid, username.lower(), digest, salt, policyholder_id, _now().isoformat()))
    return uid


def username_taken(conn, username: str) -> bool:
    return conn.execute("SELECT 1 FROM users WHERE username = ?", (username.lower(),)).fetchone() is not None


def authenticate(conn, username: str, password: str) -> Optional[dict]:
    r = conn.execute("SELECT * FROM users WHERE username = ?", (username.strip().lower(),)).fetchone()
    if not r:
        hash_password(password)  # equalise timing for unknown users
        return None
    return dict(r) if verify_password(password, r["password_hash"], r["password_salt"]) else None


def start_session(conn, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    now = _now()
    conn.execute("INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?,?,?,?)",
                 (hashlib.sha256(token.encode()).hexdigest(), user_id, now.isoformat(), (now + timedelta(hours=SESSION_HOURS)).isoformat()))
    conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now.isoformat(), user_id))
    conn.commit()
    return token


def user_for_token(conn, token: str) -> Optional[dict]:
    r = conn.execute(
        """SELECT u.id, u.username, u.policyholder_id, s.expires_at FROM sessions s JOIN users u ON u.id = s.user_id
           WHERE s.token_hash = ?""", (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    if not r or datetime.fromisoformat(r["expires_at"]) < _now():
        return None
    return dict(r)


def end_session(conn, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),))
    conn.commit()


DEMO_USERS = [("daniel", "Daniel@123", "ph-daniel"), ("priya", "Priya@123", "ph-priya")]


def ensure_demo_users(conn) -> None:
    """Fictional demo logins (shown on the login page). Idempotent; also upgrades older DBs."""
    for username, password, ph in DEMO_USERS:
        exists_ph = conn.execute("SELECT 1 FROM policyholders WHERE id = ?", (ph,)).fetchone()
        if exists_ph and not username_taken(conn, username):
            create_user(conn, username, password, ph)
    conn.commit()
