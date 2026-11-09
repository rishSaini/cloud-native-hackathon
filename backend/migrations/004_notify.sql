-- Live updates (R9): every new notification wakes the API replicas.
-- The payload is "<attendee_id>:<notification id>" only, never the content.
CREATE FUNCTION notify_affinity() RETURNS trigger AS $$
BEGIN
  PERFORM pg_notify('affinity', NEW.attendee_id || ':' || NEW.id);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER notifications_notify AFTER INSERT ON notifications
  FOR EACH ROW EXECUTE FUNCTION notify_affinity();
