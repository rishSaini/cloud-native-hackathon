-- Where each placement request stands (R6). Written by the controller, read by the API.
CREATE TABLE placements (
  attendee_id   TEXT NOT NULL REFERENCES attendees(id) ON DELETE CASCADE,
  slot          TEXT NOT NULL,
  pod_name      TEXT NOT NULL,
  status        TEXT NOT NULL CHECK (status IN ('Pending', 'Scheduled')),
  node          TEXT,
  reason        TEXT,               -- plain language, for this attendee only
  scheduler_message TEXT,           -- raw kube-scheduler text, for this attendee's kubectl view only
  options       JSONB NOT NULL DEFAULT '[]'::jsonb,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (attendee_id, slot)
);
