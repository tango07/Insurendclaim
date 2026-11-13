-- InsureNdClaim MVP schema.
-- Kept to portable SQL (no SQLite-only types beyond TEXT/INTEGER/REAL) so it can move to PostgreSQL.
-- IDs are TEXT (UUID strings) to avoid autoincrement dialect differences.

-- Fictional insurers (carriers) that issue policies.
CREATE TABLE IF NOT EXISTS insurers (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    short_name    TEXT NOT NULL,
    claims_phone  TEXT NOT NULL,
    claims_email  TEXT NOT NULL,
    website       TEXT NOT NULL,
    address       TEXT NOT NULL,
    claims_hours  TEXT NOT NULL,
    brand_color   TEXT NOT NULL DEFAULT '#0f6e66'
);

CREATE TABLE IF NOT EXISTS adjusters (
    id               TEXT PRIMARY KEY,
    insurer_id       TEXT NOT NULL REFERENCES insurers(id) ON DELETE CASCADE,
    full_name        TEXT NOT NULL,
    specialization   TEXT NOT NULL,      -- motor | property | devices
    office_location  TEXT NOT NULL,
    phone            TEXT NOT NULL,
    email            TEXT NOT NULL,
    languages        TEXT NOT NULL,
    years_experience INTEGER NOT NULL,
    bio              TEXT
);

CREATE TABLE IF NOT EXISTS repair_partners (
    id           TEXT PRIMARY KEY,
    insurer_id   TEXT NOT NULL REFERENCES insurers(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    kind         TEXT NOT NULL,          -- garage | glass | plumber | restoration | device_repair
    address      TEXT NOT NULL,
    distance_km  REAL NOT NULL,
    rating       REAL NOT NULL,
    phone        TEXT NOT NULL,
    services     TEXT NOT NULL,
    hours        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS policyholders (
    id            TEXT PRIMARY KEY,
    full_name     TEXT NOT NULL,
    photo_url     TEXT,
    city          TEXT,
    is_sample     INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS policies (
    id              TEXT PRIMARY KEY,
    policyholder_id TEXT NOT NULL REFERENCES policyholders(id) ON DELETE CASCADE,
    insurer_id      TEXT NOT NULL REFERENCES insurers(id),
    policy_number   TEXT NOT NULL UNIQUE,
    policy_type     TEXT NOT NULL,          -- auto | home | gadget ...
    product_name    TEXT NOT NULL,
    status          TEXT NOT NULL,          -- active | pending
    start_date      TEXT NOT NULL,
    end_date        TEXT NOT NULL,
    summary         TEXT,
    wording_available INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS insured_assets (
    id          TEXT PRIMARY KEY,
    policy_id   TEXT NOT NULL REFERENCES policies(id) ON DELETE CASCADE,
    asset_type  TEXT NOT NULL,              -- vehicle | property | device
    name        TEXT NOT NULL,
    details     TEXT NOT NULL DEFAULT '{}'  -- JSON object of display attributes
);

CREATE TABLE IF NOT EXISTS coverages (
    id                TEXT PRIMARY KEY,
    policy_id         TEXT NOT NULL REFERENCES policies(id) ON DELETE CASCADE,
    code              TEXT NOT NULL,
    name              TEXT NOT NULL,
    description       TEXT NOT NULL,
    limit_amount      REAL,
    limit_note        TEXT,
    deductible_amount REAL,
    tags              TEXT NOT NULL DEFAULT ''  -- comma-separated claim category keys
);

CREATE TABLE IF NOT EXISTS exclusions (
    id         TEXT PRIMARY KEY,
    policy_id  TEXT NOT NULL REFERENCES policies(id) ON DELETE CASCADE,
    code       TEXT NOT NULL,
    text       TEXT NOT NULL,
    tags       TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS policy_conditions (
    id         TEXT PRIMARY KEY,
    policy_id  TEXT NOT NULL REFERENCES policies(id) ON DELETE CASCADE,
    code       TEXT NOT NULL,
    text       TEXT NOT NULL,
    tags       TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS claims (
    id              TEXT PRIMARY KEY,
    claim_number    TEXT NOT NULL UNIQUE,
    policyholder_id TEXT NOT NULL REFERENCES policyholders(id) ON DELETE CASCADE,
    policy_id       TEXT NOT NULL REFERENCES policies(id),
    asset_id        TEXT NOT NULL REFERENCES insured_assets(id),
    category        TEXT NOT NULL,
    incident_date   TEXT,
    incident_location TEXT,
    description     TEXT NOT NULL,          -- user-provided, verbatim
    summary         TEXT NOT NULL,          -- user-reviewed (may be AI-drafted)
    next_steps      TEXT NOT NULL DEFAULT '[]',     -- JSON list (user-reviewed)
    documents_to_collect TEXT NOT NULL DEFAULT '[]',-- JSON list (user-reviewed)
    ai_suggestion   TEXT,                   -- JSON snapshot of original AI output, for audit
    status          TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claim_attachments (
    id                TEXT PRIMARY KEY,
    claim_id          TEXT REFERENCES claims(id) ON DELETE CASCADE,  -- NULL until linked on submit
    owner_id          TEXT NOT NULL REFERENCES policyholders(id) ON DELETE CASCADE,
    original_filename TEXT NOT NULL,
    content_type      TEXT NOT NULL,
    size_bytes        INTEGER NOT NULL,
    storage_key       TEXT NOT NULL,
    uploaded_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claim_events (
    id          TEXT PRIMARY KEY,
    claim_id    TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    status      TEXT NOT NULL,
    title       TEXT NOT NULL,
    detail      TEXT,
    actor       TEXT NOT NULL,              -- policyholder | system | adjuster
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS appointments (
    id               TEXT PRIMARY KEY,
    reference        TEXT NOT NULL UNIQUE,
    adjuster_id      TEXT NOT NULL REFERENCES adjusters(id),
    policyholder_id  TEXT NOT NULL REFERENCES policyholders(id) ON DELETE CASCADE,
    policy_id        TEXT NOT NULL REFERENCES policies(id),
    claim_id         TEXT REFERENCES claims(id),
    slot_start       TEXT NOT NULL,          -- local time, ISO "YYYY-MM-DDTHH:MM"
    duration_minutes INTEGER NOT NULL,
    mode             TEXT NOT NULL,          -- audio | video | onsite | chat
    contact_name     TEXT NOT NULL,          -- shared with the adjuster
    contact_phone    TEXT NOT NULL,          -- shared with the adjuster
    meeting_location TEXT,
    meeting_link     TEXT,
    instructions     TEXT NOT NULL DEFAULT '[]',  -- JSON list
    directions       TEXT,
    shared_attachment_ids TEXT NOT NULL DEFAULT '[]',
    status           TEXT NOT NULL,          -- confirmed | cancelled
    created_at       TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_appt_slot ON appointments(adjuster_id, slot_start) WHERE status = 'confirmed';

CREATE INDEX IF NOT EXISTS idx_policies_holder ON policies(policyholder_id);
CREATE INDEX IF NOT EXISTS idx_assets_policy ON insured_assets(policy_id);
CREATE INDEX IF NOT EXISTS idx_claims_holder ON claims(policyholder_id);
CREATE INDEX IF NOT EXISTS idx_events_claim ON claim_events(claim_id);

-- Login accounts (one per policyholder profile). Passwords are PBKDF2-SHA256 hashed with a per-user salt.
CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    password_salt   TEXT NOT NULL,
    policyholder_id TEXT NOT NULL UNIQUE REFERENCES policyholders(id) ON DELETE CASCADE,
    created_at      TEXT NOT NULL,
    last_login_at   TEXT
);

-- Opaque bearer tokens; only the SHA-256 of the token is stored.
CREATE TABLE IF NOT EXISTS sessions (
    token_hash  TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL
);
