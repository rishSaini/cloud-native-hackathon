"""Apply SQL migrations from backend/migrations/, in order. Safe to rerun (R3).

    python -m app.db.migrate                # fails if the database can't be reached
    python -m app.db.migrate --best-effort  # app initContainer: skips if it can't be reached

The app Deployment runs this as an initContainer, so every rollout brings the
schema up to date (a recreated database used to stay empty until someone ran a
db-migrate Job by hand). --best-effort keeps the app starting when the database
doesn't exist yet or is down; a migration that reaches the database and fails
still exits non-zero, so a broken migration stops the rollout.

Each file runs once, in its own transaction, and is recorded in
schema_migrations. An advisory lock stops two runners (two replicas) from racing.
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import psycopg

from app.db import database_url

log = logging.getLogger("affinity.db")
MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
LOCK_ID = 727274  # any constant shared by all runners


class DatabaseUnavailable(Exception):
    """The database isn't configured or couldn't be reached."""


def migration_files(folder: Path = MIGRATIONS) -> list[Path]:
    return sorted(folder.glob("[0-9][0-9][0-9]_*.sql"))


def pending(files: list[Path], applied: set[str]) -> list[Path]:
    return [f for f in files if f.name not in applied]


def connect(url: str, attempts: int = 10) -> psycopg.Connection:
    """The database may still be starting, so retry for a while."""
    for attempt in range(1, attempts + 1):
        try:
            return psycopg.connect(url, autocommit=True)
        except psycopg.OperationalError as err:
            if attempt == attempts:
                raise DatabaseUnavailable(f"database not reachable after {attempts} attempts") from err
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.db.migrate")
    parser.add_argument("--best-effort", action="store_true",
                        help="exit 0 when the database isn't configured or can't be reached")
    args = parser.parse_args(argv)

    if not os.getenv("DATABASE_URL"):
        if args.best_effort:
            log.warning("DATABASE_URL is not set; skipping migrations")
            return 0
        log.error("DATABASE_URL is not set (Secret db-app, key uri)")
        return 1
    try:
        done = migrate()
    except DatabaseUnavailable as err:
        if args.best_effort:
            log.warning("%s; skipping migrations", err)
            return 0
        raise
    print(f"Applied {len(done)} migration(s): {done}" if done else "Database is up to date.")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.exit(main())
