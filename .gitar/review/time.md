# Time zones

Conference times are in America/Denver and are stored with an explicit offset
(`2026-11-10T14:30:00-07:00`). Flag any Python code that formats or compares
session times with a naive `datetime`, `datetime.now()` without a time zone, or the
server's local time. Use `datetime.now(timezone.utc)` or `ZoneInfo("America/Denver")`.
