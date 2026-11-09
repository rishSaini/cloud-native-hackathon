-- Affinity schema (R3), from docs/AFFINITY.md "Data model" plus the tables the
-- controller needs. Private card data lives only here, encrypted (R4).

CREATE TABLE attendees (
  id            TEXT PRIMARY KEY,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE cards (
  attendee_id   TEXT PRIMARY KEY REFERENCES attendees(id) ON DELETE CASCADE,
  ciphertext    BYTEA NOT NULL,
  nonce         BYTEA NOT NULL,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE card_grants (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id      TEXT NOT NULL REFERENCES attendees(id) ON DELETE CASCADE,
  viewer_id     TEXT REFERENCES attendees(id) ON DELETE CASCADE,
  reason        TEXT NOT NULL CHECK (reason IN ('group', 'qr')),
  expires_at    TIMESTAMPTZ NOT NULL,
  revoked_at    TIMESTAMPTZ
);

CREATE TABLE capabilities (
  attendee_id   TEXT NOT NULL REFERENCES attendees(id) ON DELETE CASCADE,
  capability    TEXT NOT NULL,  -- opaque code such as cap-c1, never a meaning
  PRIMARY KEY (attendee_id, capability)
);

CREATE TABLE groups (
  id            TEXT PRIMARY KEY,
  slot          TEXT NOT NULL,
  table_id      TEXT
);

CREATE TABLE group_members (
  group_id      TEXT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  attendee_id   TEXT NOT NULL REFERENCES attendees(id) ON DELETE CASCADE,
  checked_in_at TIMESTAMPTZ,
  PRIMARY KEY (group_id, attendee_id)
);

CREATE TABLE connections (
  attendee_a    TEXT NOT NULL REFERENCES attendees(id) ON DELETE CASCADE,
  attendee_b    TEXT NOT NULL REFERENCES attendees(id) ON DELETE CASCADE,
  met_at_label  TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (attendee_a, attendee_b)
);

CREATE TABLE blocks (
  blocker_id    TEXT NOT NULL REFERENCES attendees(id) ON DELETE CASCADE,
  blocked_id    TEXT NOT NULL REFERENCES attendees(id) ON DELETE CASCADE,
  PRIMARY KEY (blocker_id, blocked_id)
);

-- Controller tables (rishabh.md R3)

CREATE TABLE placement_requests (
  attendee_id   TEXT NOT NULL REFERENCES attendees(id) ON DELETE CASCADE,
  slot          TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (attendee_id, slot)
);

CREATE TABLE break_rsvps (
  break_id      TEXT NOT NULL,
  attendee_id   TEXT NOT NULL REFERENCES attendees(id) ON DELETE CASCADE,
  PRIMARY KEY (break_id, attendee_id)
);

CREATE TABLE notifications (
  id            BIGSERIAL PRIMARY KEY,
  attendee_id   TEXT NOT NULL REFERENCES attendees(id) ON DELETE CASCADE,
  kind          TEXT NOT NULL,
  payload       JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX notifications_attendee_idx ON notifications (attendee_id, id);

-- The move-once rule: a person is moved at most once per slot unless the room closes.
CREATE TABLE moves (
  attendee_id   TEXT NOT NULL REFERENCES attendees(id) ON DELETE CASCADE,
  slot          TEXT NOT NULL,
  count         INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (attendee_id, slot)
);
