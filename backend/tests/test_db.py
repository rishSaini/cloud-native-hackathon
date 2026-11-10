"""R3: migration runner. The live test runs only when TEST_DATABASE_URL is set."""

import os
from pathlib import Path

import pytest

from app.db import migrate


def test_migrations_are_numbered_and_ordered():
    files = migrate.migration_files()
    assert files and files[0].name == "001_init.sql"
    assert [f.name for f in files] == sorted(f.name for f in files)


def test_pending_skips_applied_files():
    files = [Path("001_init.sql"), Path("002_more.sql")]
    assert migrate.pending(files, {"001_init.sql"}) == [Path("002_more.sql")]
    assert migrate.pending(files, {"001_init.sql", "002_more.sql"}) == []


def test_schema_has_the_controller_tables():
    sql = (migrate.MIGRATIONS / "001_init.sql").read_text()
    for table in ("attendees", "cards", "capabilities", "placement_requests", "break_rsvps", "notifications", "moves"):
        assert f"CREATE TABLE {table} (" in sql


def test_best_effort_skips_without_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert migrate.main(["--best-effort"]) == 0
    assert migrate.main([]) == 1


def test_best_effort_skips_when_database_is_unreachable(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db-rw:5432/app")

    def unreachable():
        raise migrate.DatabaseUnavailable("database not reachable after 10 attempts")

    monkeypatch.setattr(migrate, "migrate", unreachable)
    assert migrate.main(["--best-effort"]) == 0
    with pytest.raises(migrate.DatabaseUnavailable):
        migrate.main([])


def test_best_effort_still_fails_on_a_broken_migration(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db-rw:5432/app")

    def broken():
        raise RuntimeError("syntax error in 007_bad.sql")

    monkeypatch.setattr(migrate, "migrate", broken)
    with pytest.raises(RuntimeError):
        migrate.main(["--best-effort"])


def test_connect_reports_unavailable_after_retries(monkeypatch):
    def refuse(*args, **kwargs):
        raise migrate.psycopg.OperationalError("connection refused")

    monkeypatch.setattr(migrate.psycopg, "connect", refuse)
    monkeypatch.setattr(migrate.time, "sleep", lambda s: None)
    with pytest.raises(migrate.DatabaseUnavailable):
        migrate.connect("postgresql://u:p@nowhere:5432/app", attempts=2)


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="needs TEST_DATABASE_URL")
def test_migrate_twice_on_a_real_database():
    url = os.environ["TEST_DATABASE_URL"]
    migrate.migrate(url)  # first run may apply files, or find them applied
    assert migrate.migrate(url) == []  # the second run changes nothing
