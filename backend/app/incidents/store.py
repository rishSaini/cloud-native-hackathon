"""Incidents in the Elasticsearch `incidents` index (K11)."""

from datetime import datetime, timezone

from elasticsearch import ConflictError, NotFoundError
from opentelemetry import metrics

from app.search import mappings as m

KINDS = {"captions": "captions_down", "access": "access_blocked"}  # kind -> the signal that opens it
ACTIVE = ("open", "acknowledged")
NEXT = {"open": {"acknowledged", "resolved"}, "acknowledged": {"resolved"}, "resolved": set()}

_open_count = 0
metrics.get_meter("affinity").create_observable_gauge(
    "affinity_incidents_open",
    callbacks=[lambda options: [metrics.Observation(_open_count)]],
    description="Accessibility incidents not yet resolved",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def refresh_gauge(es) -> int:
    global _open_count
    try:
        _open_count = es.count(index=m.INCIDENTS, query={"terms": {"state": list(ACTIVE)}})["count"]
    except NotFoundError:
        _open_count = 0
    return _open_count


def active_incident(es, room: str, kind: str) -> dict | None:
    try:
        hits = es.search(
            index=m.INCIDENTS, size=1,
            query={"bool": {"filter": [{"term": {"room": room}}, {"term": {"kind": kind}}, {"terms": {"state": list(ACTIVE)}}]}},
        )["hits"]["hits"]
    except NotFoundError:
        return None
    return hits[0]["_source"] if hits else None


def _resolved_count(es, room: str, kind: str) -> int:
    try:
        return es.count(
            index=m.INCIDENTS,
            query={"bool": {"filter": [{"term": {"room": room}}, {"term": {"kind": kind}}, {"term": {"state": "resolved"}}]}},
        )["count"]
    except NotFoundError:
        return 0


def open_incident(es, room: str, kind: str) -> dict:
    """Open an incident, unless this room already has an active one of this kind.

    The id is deterministic: one more than the resolved incidents for this room
    and kind. Writers racing past the active check all see the same resolved
    count, so they pick the same id, and op_type=create lets only one of them
    write it; the others get a conflict and return the winner's doc. (Counting
    all incidents would not work: a loser that counts after the winner's write
    would pick the next id and open a duplicate.)
    """
    existing = active_incident(es, room, kind)
    if existing:
        return existing
    seq = _resolved_count(es, room, kind) + 1
    doc = {"id": f"inc-{room}-{kind}-{seq}", "room": room, "kind": kind, "state": "open", "opened_at": _now()}
    try:
        es.create(index=m.INCIDENTS, id=doc["id"], document=doc, refresh="wait_for")
    except ConflictError:
        # Another writer opened it first. GET is real-time, so it sees that doc.
        return es.get(index=m.INCIDENTS, id=doc["id"])["_source"]
    refresh_gauge(es)
    return doc


def list_incidents(es, include_resolved: bool = False) -> list[dict]:
    query = {"match_all": {}} if include_resolved else {"terms": {"state": list(ACTIVE)}}
    try:
        hits = es.search(index=m.INCIDENTS, size=200, query=query, sort=[{"opened_at": "desc"}])["hits"]["hits"]
    except NotFoundError:
        return []
    return [h["_source"] for h in hits]


class TransitionError(ValueError):
    pass


def transition(es, incident_id: str, new_state: str) -> dict:
    try:
        doc = es.get(index=m.INCIDENTS, id=incident_id)["_source"]
    except NotFoundError as err:
        raise KeyError(incident_id) from err
    if new_state not in NEXT[doc["state"]]:
        raise TransitionError(f"cannot go from {doc['state']} to {new_state}")
    stamp = _now()
    doc["state"] = new_state
    doc[f"{new_state}_at"] = stamp
    es.update(index=m.INCIDENTS, id=incident_id, doc={"state": new_state, f"{new_state}_at": stamp}, refresh="wait_for")
    if new_state == "resolved":
        clear_room_signal(es, doc["room"], doc["kind"], stamp)
    refresh_gauge(es)
    return doc


def clear_room_signal(es, room: str, kind: str, stamp: str) -> None:
    """Staff fixed it: the room's signal clears, and reports before now stop counting (K10)."""
    signals = {"captions": "working"} if kind == "captions" else {"access_blocked": False}
    es.update(
        index=m.ROOM_STATE, id=room, refresh="wait_for",
        doc={"room": room, "signals": signals, "changed_at": stamp,
             "confidence": {"cleared": {KINDS[kind]: stamp}}},
        doc_as_upsert=True,
    )
