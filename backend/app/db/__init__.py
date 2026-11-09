"""Postgres access (owner: Rishabh, R3).

The pool opens on first use, never at import, so /healthz and /readyz never
touch the database. DATABASE_URL comes from Secret db-app (key uri), which the
CloudNativePG operator creates.
"""

import os
import threading

from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None
_lock = threading.Lock()


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (Secret db-app, key uri)")
    return url


def pool() -> ConnectionPool:
    """The shared connection pool. Usage: with pool().connection() as conn: ..."""
    global _pool
    with _lock:
        if _pool is None:
            # Waits for the database at first use, so the app survives a slow
            # operator (pods can start before db-app exists).
            _pool = ConnectionPool(database_url(), min_size=1, max_size=5, timeout=30, open=True)
    return _pool
