"""Where cards live (R4): Postgres, encrypted. The routes use it through get_store()."""

from app.cards.crypto import decrypt, encrypt


class PostgresCardStore:
    def __init__(self, pool):
        self.pool = pool

    def create_attendee(self, attendee_id: str) -> bool:
        """False if the ID is taken."""
        with self.pool().connection() as conn:
            row = conn.execute(
                "INSERT INTO attendees (id) VALUES (%s) ON CONFLICT DO NOTHING RETURNING id", (attendee_id,)
            ).fetchone()
        return row is not None

    def ensure_attendee(self, attendee_id: str) -> None:
        with self.pool().connection() as conn:
            conn.execute("INSERT INTO attendees (id) VALUES (%s) ON CONFLICT DO NOTHING", (attendee_id,))

    def save(self, attendee_id: str, card: dict, codes: list[str]) -> None:
        ciphertext, nonce = encrypt(attendee_id, card)
        with self.pool().connection() as conn, conn.transaction():
            conn.execute("INSERT INTO attendees (id) VALUES (%s) ON CONFLICT DO NOTHING", (attendee_id,))
            conn.execute(
                "INSERT INTO cards (attendee_id, ciphertext, nonce) VALUES (%s, %s, %s)"
                " ON CONFLICT (attendee_id) DO UPDATE SET ciphertext = EXCLUDED.ciphertext,"
                " nonce = EXCLUDED.nonce, updated_at = now()",
                (attendee_id, ciphertext, nonce),
            )
            conn.execute("DELETE FROM capabilities WHERE attendee_id = %s", (attendee_id,))
            for code in codes:
                conn.execute("INSERT INTO capabilities (attendee_id, capability) VALUES (%s, %s)", (attendee_id, code))

    def load(self, attendee_id: str) -> dict | None:
        with self.pool().connection() as conn:
            row = conn.execute("SELECT ciphertext, nonce FROM cards WHERE attendee_id = %s", (attendee_id,)).fetchone()
        return decrypt(attendee_id, bytes(row[0]), bytes(row[1])) if row else None

    def delete(self, attendee_id: str) -> None:
        with self.pool().connection() as conn, conn.transaction():
            conn.execute("DELETE FROM cards WHERE attendee_id = %s", (attendee_id,))
            conn.execute("DELETE FROM capabilities WHERE attendee_id = %s", (attendee_id,))
            conn.execute("UPDATE card_grants SET revoked_at = now() WHERE owner_id = %s AND revoked_at IS NULL", (attendee_id,))


def get_store():
    from app.db import pool

    return PostgresCardStore(pool)
