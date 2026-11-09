ALTER TABLE group_members
  ADD COLUMN check_in_status TEXT
  CHECK (check_in_status IN ('here', 'on-the-way', 'late'));

UPDATE group_members
SET check_in_status = 'here'
WHERE checked_in_at IS NOT NULL;
