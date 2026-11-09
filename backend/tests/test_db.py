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


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="needs TEST_DATABASE_URL")
def test_migrate_twice_on_a_real_database():
    url = os.environ["TEST_DATABASE_URL"]
    migrate.migrate(url)  # first run may apply files, or find them applied
    assert migrate.migrate(url) == []  # the second run changes nothing
