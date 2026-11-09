"""The `people` index: consented interest text under a random attendee ID (K7).

Never store a name, card text or access needs here. The index mapping is
strict, so Elasticsearch rejects any other field.
The document ID is the attendee ID, so an upsert replaces the old interests.
"""

from datetime import datetime, timezone

from elasticsearch import NotFoundError

from app.es import get_es
from app.search import mappings as m


def upsert_person(attendee_id: str, interests: str) -> None:
    interests = (interests or "").strip()
    if not interests:
        # No interests means nothing to match on.
        delete_person(attendee_id)
        return
    get_es().index(
        index=m.PEOPLE,
        id=attendee_id,
        document={
            "attendee_id": attendee_id,
            "interests": interests,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def delete_person(attendee_id: str) -> None:
    try:
        get_es().delete(index=m.PEOPLE, id=attendee_id)
    except NotFoundError:
        pass
