-- Sharing, connections and safety (R11).
-- A connection is saved only when both people propose it; until then it is a proposal.
CREATE TABLE connection_proposals (
  from_id     TEXT NOT NULL REFERENCES attendees(id) ON DELETE CASCADE,
  to_id       TEXT NOT NULL REFERENCES attendees(id) ON DELETE CASCADE,
  group_id    TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (from_id, to_id)
);

-- For organizers under the Code of Conduct. Never logged.
CREATE TABLE safety_reports (
  id          BIGSERIAL PRIMARY KEY,
  reporter_id TEXT REFERENCES attendees(id) ON DELETE SET NULL,
  about_id    TEXT,
  kind        TEXT NOT NULL,
  details     TEXT NOT NULL DEFAULT '',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
