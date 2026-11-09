-- Breaks and when their groups form (R10). Times are America/Denver with offsets.
CREATE TABLE breaks (
  id                TEXT PRIMARY KEY,
  starts_at         TIMESTAMPTZ NOT NULL,
  ends_at           TIMESTAMPTZ NOT NULL,
  form_requested_at TIMESTAMPTZ,      -- staff "form groups now" (demo)
  formed_at         TIMESTAMPTZ
);
INSERT INTO breaks (id, starts_at, ends_at) VALUES
  ('brk-tue-1000', '2026-11-10T10:00:00-07:00', '2026-11-10T10:30:00-07:00'),
  ('brk-tue-1530', '2026-11-10T15:30:00-07:00', '2026-11-10T16:00:00-07:00');
