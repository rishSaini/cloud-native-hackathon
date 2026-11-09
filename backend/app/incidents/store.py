"""Incidents in the Elasticsearch `incidents` index (K11)."""

import uuid
from datetime import datetime, timezone

from elasticsearch import NotFoundError
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


def open_incident(es, room: str, kind: str) -> dict:
    """Open an incident, unless this room already has an active one of this kind."""
    existing = active_incident(es, room, kind)
    if existing:
        return existing
    doc = {"id": f"inc-{uuid.uuid4().hex[:10]}", "room": room, "kind": kind, "state": "open", "opened_at": _now()}
    es.index(index=m.INCIDENTS, id=doc["id"], document=doc, refresh="wait_for")
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
