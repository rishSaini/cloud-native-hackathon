-- Human insights (K17). Counts only: no attendee IDs, so nothing here is personal
-- and "delete everywhere" has nothing to delete.

-- Seats taken in each room, written by the controller only when the count changes.
CREATE TABLE occupancy_samples (
  node          TEXT NOT NULL,
  slot          TEXT NOT NULL,
  room          TEXT NOT NULL,
  seats         INTEGER NOT NULL,
  taken         INTEGER NOT NULL,
  at            TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (node, at)
);
CREATE INDEX occupancy_samples_slot_idx ON occupancy_samples (slot, at);

-- One row for each first seat: how long the person waited, and whether they
-- asked for any access need. Which need, and who, are never stored.
CREATE TABLE seat_waits (
  id            BIGSERIAL PRIMARY KEY,
  slot          TEXT NOT NULL,
  need_present  BOOLEAN NOT NULL,
  seconds       DOUBLE PRECISION NOT NULL,
  at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX seat_waits_slot_idx ON seat_waits (slot, at);
