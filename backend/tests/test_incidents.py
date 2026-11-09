"""K11: incidents open once, move forward only, and resolving clears the room."""

from datetime import datetime, timedelta, timezone

import pytest
from elastic_transport import ApiResponseMeta, HttpHeaders
from elasticsearch import NotFoundError
from fastapi.testclient import TestClient

from app.es import get_es
from app.incidents import store
from app.main import app
from app.reports import state


def not_found():
    meta = ApiResponseMeta(status=404, http_version="1.1", headers=HttpHeaders(), duration=0.0, node=None)
    return NotFoundError("missing", meta=meta, body={})


class FakeIncidentsES:
    """Just enough of ES for incidents: one dict per index, term filters on simple fields."""

    def __init__(self):
        self.docs = {"incidents": {}, "room-state": {}}

    @staticmethod
    def _match(doc, query):
        if "match_all" in query:
            return True
        if "terms" in query:
            (field, values), = query["terms"].items()
            return doc.get(field) in values
        for f in query["bool"]["filter"]:
            kind, cond = next(iter(f.items()))
            (field, value), = cond.items()
            if (kind == "term" and doc.get(field) != value) or (kind == "terms" and doc.get(field) not in value):
                return False
        return True

    def search(self, index, query, size=10, sort=None):
        hits = [{"_source": d} for d in self.docs[index].values() if self._match(d, query)]
        return {"hits": {"hits": hits[:size]}}

    def count(self, index, query):
        return {"count": sum(self._match(d, query) for d in self.docs[index].values())}

    def index(self, index, id, document, refresh=None):
        self.docs[index][id] = dict(document)

    def get(self, index, id):
        if id not in self.docs[index]:
            raise not_found()
        return {"_source": dict(self.docs[index][id])}

    def update(self, index, id, doc, refresh=None, doc_as_upsert=False):
        target = self.docs[index].setdefault(id, {})
        for k, v in doc.items():
            if isinstance(v, dict) and isinstance(target.get(k), dict):
                target[k] = {**target[k], **v}
            else:
                target[k] = v


@pytest.fixture
def es():
    return FakeIncidentsES()


def test_one_active_incident_per_room_and_kind(es):
    first = store.open_incident(es, "room-251", "captions")
    again = store.open_incident(es, "room-251", "captions")
    other = store.open_incident(es, "room-251", "access")
    assert again["id"] == first["id"] and other["id"] != first["id"]
    assert store.refresh_gauge(es) == 2


def test_transitions_move_forward_only(es):
    inc = store.open_incident(es, "room-101", "captions")
    assert store.transition(es, inc["id"], "acknowledged")["state"] == "acknowledged"
    with pytest.raises(store.TransitionError):
        store.transition(es, inc["id"], "acknowledged")
    assert store.transition(es, inc["id"], "resolved")["resolved_at"]
    with pytest.raises(store.TransitionError):
        store.transition(es, inc["id"], "acknowledged")
    with pytest.raises(KeyError):
        store.transition(es, "inc-nope", "resolved")


def test_resolving_captions_marks_the_room_working_and_cleared(es):
    inc = store.open_incident(es, "room-101", "captions")
    store.transition(es, inc["id"], "resolved")
    room = es.docs["room-state"]["room-101"]
    assert room["signals"]["captions"] == "working"
    assert "captions_down" in room["confidence"]["cleared"]
    assert store.refresh_gauge(es) == 0
    # A new incident of the same kind can open after resolution.
    assert store.open_incident(es, "room-101", "captions")["id"] != inc["id"]


def test_cleared_reports_stop_counting():
    now = datetime(2026, 11, 10, 14, 30, tzinfo=timezone.utc)
    minute = lambda ago: {"key": (now - timedelta(minutes=ago)).timestamp() * 1000, "doc_count": 3}
    agg = {"signals": {"buckets": [{"key": "captions_down", "per_minute": {"buckets": [minute(2)]}}]}}
    assert state.confidences(agg, now)["captions_down"] > 2.5
    cleared = {"captions_down": (now - timedelta(minutes=1)).isoformat()}
    assert state.confidences(agg, now, cleared)["captions_down"] == 0.0


def test_recompute_opens_an_incident_when_captions_go_down(es):
    opened = []
    import app.incidents.store as s

    original = s.open_incident
    s.open_incident = lambda es_, room, kind: opened.append((room, kind))
    try:
        state.open_incidents(es, "room-155", {"signals": {"captions": "working"}},
                             {"signals": {"captions": "down", "very_loud": False, "access_blocked": True}})
    finally:
        s.open_incident = original
    assert opened == [("room-155", "captions"), ("room-155", "access")]


# ---- routes ----

@pytest.fixture
def staff_client(es, monkeypatch):
    monkeypatch.setenv("STAFF_TOKEN", "s3cret-staff")
    app.dependency_overrides[get_es] = lambda: es
    yield TestClient(app), es
    app.dependency_overrides.clear()


def test_staff_routes_need_the_token(staff_client):
    client, _ = staff_client
    assert client.get("/api/staff/incidents").status_code == 401
    assert client.get("/api/staff/incidents", headers={"X-Staff-Token": "wrong"}).status_code == 401
    assert client.get("/api/staff/login", params={"token": "wrong"}).status_code == 401


def test_staff_cookie_login_then_list_and_patch(staff_client):
    client, es = staff_client
    inc = store.open_incident(es, "room-251", "captions")
    assert client.get("/api/staff/login", params={"token": "s3cret-staff"}).status_code == 200
    listed = client.get("/api/staff/incidents").json()
    assert listed[0] == {**listed[0], "id": inc["id"], "room": "room-251", "kind": "captions", "state": "open"}
    assert client.patch(f"/api/staff/incidents/{inc['id']}", json={"state": "acknowledged"}).status_code == 200
    assert client.patch(f"/api/staff/incidents/{inc['id']}", json={"state": "acknowledged"}).status_code == 409
    assert client.patch(f"/api/staff/incidents/{inc['id']}", json={"state": "open"}).status_code == 422
    assert client.patch(f"/api/staff/incidents/{inc['id']}", json={"state": "resolved"}).json()["state"] == "resolved"
    assert client.get("/api/staff/incidents").json() == []


def test_staff_resolution_keeps_captions_working_for_30_minutes():
    now = datetime(2026, 11, 10, 14, 30, tzinfo=timezone.utc)
    cleared = {"captions_down": (now - timedelta(minutes=10)).isoformat()}
    assert state.staff_confirmed_captions("unknown", cleared, now) == "working"
    assert state.staff_confirmed_captions("down", cleared, now) == "down"
    old = {"captions_down": (now - timedelta(minutes=45)).isoformat()}
    assert state.staff_confirmed_captions("unknown", old, now) == "unknown"
