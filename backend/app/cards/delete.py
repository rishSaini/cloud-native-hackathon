"""Deletion everywhere (R12): DELETE /api/card removes the attendee from every store.

- Postgres: the attendee row; every table references it ON DELETE CASCADE
  (card, capabilities, grants, placements, requests, RSVPs, groups, notifications).
- Elasticsearch: Karthik's delete_person removes the people document. Room
  reports hold only a hash, so there is nothing else to remove.
- Kubernetes: the API has no cluster access, so the controller's cleanup
  reconciler deletes Pods whose attendee no longer exists (app.controller.cleanup).
"""

import logging

log = logging.getLogger("affinity.cards")


def delete_from_postgres(attendee_id: str) -> None:
    from app.db import pool

    with pool().connection() as conn:
        conn.execute("DELETE FROM attendees WHERE id = %s", (attendee_id,))


def delete_from_search(attendee_id: str) -> None:
    from app.search.people import delete_person

    try:
        delete_person(attendee_id)
    except NotImplementedError:
        log.info("people index not available yet; nothing to delete there")


def delete_everywhere(attendee_id: str, postgres=delete_from_postgres, search=delete_from_search) -> None:
    search(attendee_id)  # first: if Postgres fails, at least matching stops
    postgres(attendee_id)
