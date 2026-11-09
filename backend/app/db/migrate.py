"""Apply SQL migrations from backend/migrations/, in order. Safe to rerun (R3).

    python -m app.db.migrate      # in the cluster: Job deploy/jobs/db-migrate-001.yaml

Each file runs once, in its own transaction, and is recorded in
schema_migrations. An advisory lock stops two runners from racing.
"""

import logging
import time
from pathlib import Path

import psycopg

from app.db import database_url

log = logging.getLogger("affinity.db")
MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
LOCK_ID = 727274  # any constant shared by all runners


def migration_files(folder: Path = MIGRATIONS) -> list[Path]:
    return sorted(folder.glob("[0-9][0-9][0-9]_*.sql"))


def pending(files: list[Path], applied: set[str]) -> list[Path]:
    return [f for f in files if f.name not in applied]


def connect(url: str, attempts: int = 10) -> psycopg.Connection:
    """The database may still be starting, so retry for a while."""
    for attempt in range(1, attempts + 1):
        try:
            return psycopg.connect(url, autocommit=True)
        except psycopg.OperationalError:
            if attempt == attempts:
                raise
            log.info("database not ready (attempt %d); retrying", attempt)
            time.sleep(3)


def migrate(url: str | None = None) -> list[str]:
    applied_now = []
    with connect(url or database_url()) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                " version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
            )
            applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
            for path in pending(migration_files(), applied):
                with conn.transaction():
                    conn.execute(path.read_text())
                    conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
                applied_now.append(path.name)
                log.info("applied %s", path.name)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))
    return applied_now


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    done = migrate()
    print(f"Applied {len(done)} migration(s): {done}" if done else "Database is up to date.")
