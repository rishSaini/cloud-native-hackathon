"""Solver inputs for a break (contract, owner: Rishabh, R10)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # Karthik's module; never import it at startup.
    from app.solver import SolverPerson


def load_break_people(break_id: str, conn=None) -> list[SolverPerson]:
    """Everyone who RSVPed to `break_id`, with needs, blocks and people already met."""
    from app.db import pool
    from app.solver import SolverPerson

    def run(c):
        rows = c.execute(
            """
            SELECT r.attendee_id,
              COALESCE((SELECT array_agg(capability) FROM capabilities WHERE attendee_id = r.attendee_id), '{}'),
              COALESCE((SELECT array_agg(CASE WHEN blocker_id = r.attendee_id THEN blocked_id ELSE blocker_id END)
                        FROM blocks WHERE r.attendee_id IN (blocker_id, blocked_id)), '{}'),
              COALESCE((SELECT array_agg(DISTINCT other.attendee_id) FROM group_members mine
                        JOIN group_members other ON other.group_id = mine.group_id AND other.attendee_id <> mine.attendee_id
                        WHERE mine.attendee_id = r.attendee_id), '{}')
              || COALESCE((SELECT array_agg(CASE WHEN attendee_a = r.attendee_id THEN attendee_b ELSE attendee_a END)
                        FROM connections WHERE r.attendee_id IN (attendee_a, attendee_b)), '{}')
            FROM break_rsvps r WHERE r.break_id = %s ORDER BY r.attendee_id
            """,
            (break_id,),
        ).fetchall()
        return [SolverPerson(a, frozenset(n), frozenset(b), frozenset(m)) for a, n, b, m in rows]

    if conn is not None:
        return run(conn)
    with pool().connection() as c:
        return run(c)
