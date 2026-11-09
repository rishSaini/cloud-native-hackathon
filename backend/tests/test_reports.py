"""K9: room reports, with a fake ES and a faked signed-in attendee."""

import pytest
from fastapi.testclient import TestClient

from app.auth import attendee_hash, current_attendee_id
from app.es import get_es
from app.main import app


class FakeReportsES:
    def __init__(self):
        self.stored = []
        self.count_queries = []

    def count(self, index, query):
        self.count_queries.append(query)
        filters = {list(f.values())[0].__iter__().__next__(): f for f in query["bool"]["filter"]}
        want = {
            key: query["bool"]["filter"][i]["term"][key]
            for i, key in enumerate(("room", "signal", "reporter_hash"))
        }
        assert "@timestamp" in filters  # the time window is part of the query
        hits = [d for d in self.stored if all(d[k] == v for k, v in want.items())]
        return {"count": len(hits)}

    def index(self, index, document, op_type, refresh):
        assert index == "room-reports" and op_type == "create"
        self.stored.append(document)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("app.reports.routes.recompute_state", lambda room, es: {"status": "open"})
    es = FakeReportsES()
    app.dependency_overrides[get_es] = lambda: es
    app.dependency_overrides[current_attendee_id] = lambda: "att-7f3k"
    yield TestClient(app), es
    app.dependency_overrides.clear()


def test_report_is_stored_with_a_hash_not_the_id(client):
    c, es = client
    resp = c.post("/api/rooms/room-251/reports", json={"signal": "full", "slot": "tue-1430"})
    assert resp.status_code == 202
    doc = es.stored[0]
    assert set(doc) == {"@timestamp", "room", "signal", "reporter_hash", "slot"}
    assert doc["reporter_hash"] == attendee_hash("att-7f3k")
    assert "att-7f3k" not in str(doc)


def test_duplicate_within_two_minutes_is_429(client):
    c, _ = client
    assert c.post("/api/rooms/room-251/reports", json={"signal": "full"}).status_code == 202
    assert c.post("/api/rooms/room-251/reports", json={"signal": "full"}).status_code == 429
    # A different signal or room is still fine.
    assert c.post("/api/rooms/room-251/reports", json={"signal": "very_loud"}).status_code == 202
    assert c.post("/api/rooms/room-101/reports", json={"signal": "full"}).status_code == 202


@pytest.mark.parametrize(
    "path, body",
    [
        ("/api/rooms/room-251/reports", {"signal": "on_fire"}),
        ("/api/rooms/Room 251/reports", {"signal": "full"}),
        ("/api/rooms/room-251/reports", {"signal": "full", "slot": "tomorrow"}),
    ],
)
def test_rejects_bad_input(client, path, body):
    c, _ = client
    assert c.post(path, json=body).status_code == 422


def test_requires_a_session():
    app.dependency_overrides[get_es] = FakeReportsES
    try:
        assert TestClient(app).post("/api/rooms/room-251/reports", json={"signal": "full"}).status_code == 401
    finally:
        app.dependency_overrides.clear()
