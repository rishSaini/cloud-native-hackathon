"""Store room reports in the `room-reports` data stream (K9).

Each report holds the room, the signal, the time and a reporter hash, never an
attendee ID. The rate limit (one report per reporter, room and signal every two
minutes) is an Elasticsearch query, not app memory, because two app replicas
run at once.
"""

from datetime import UTC, datetime

from elasticsearch import NotFoundError

from app.search import mappings as m

SIGNALS = (
    "seats_available",
    "standing_room",
    "full",
    "very_loud",
    "captions_working",
    "captions_down",
    "access_blocked",
)
RATE_LIMIT = "2m"


def recently_reported(es, room: str, signal: str, reporter_hash: str) -> bool:
    try:
        resp = es.count(
            index=m.ROOM_REPORTS,
            query={
                "bool": {
                    "filter": [
                        {"term": {"room": room}},
                        {"term": {"signal": signal}},
                        {"term": {"reporter_hash": reporter_hash}},
                        {"range": {"@timestamp": {"gte": f"now-{RATE_LIMIT}"}}},
                    ]
                }
            },
        )
    except NotFoundError:
        return False
    return resp["count"] > 0


def record_report(es, room: str, signal: str, reporter_hash: str, slot: str | None = None) -> dict:
    doc = {
        "@timestamp": datetime.now(UTC).isoformat(),
        "room": room,
        "signal": signal,
        "reporter_hash": reporter_hash,
    }
    if slot:
        doc["slot"] = slot
    # Data streams only accept op_type=create. wait_for makes the report visible
    # to the next rate-limit check, even on the other replica.
    es.index(index=m.ROOM_REPORTS, document=doc, op_type="create", refresh="wait_for")
    return doc
