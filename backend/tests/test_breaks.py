from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import current_attendee_id
from app.breaks import routes
from app.cards.store import get_store


class _Result:
    def __init__(self, row=None, rows=()):
        self.row = row
        self.rows = rows

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class _Connection:
    def __init__(self, group_row=None, members=()):
        self.group_row = group_row
        self.members = members
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, params=()):
        self.calls.append((query, params))
        if query.startswith("SELECT 1 FROM breaks"):
            return _Result((1,))
        if query.startswith("INSERT INTO attendees"):
            return _Result()
        if query.startswith("INSERT INTO break_rsvps"):
            return _Result()
        if query.startswith("DELETE FROM break_rsvps"):
            return _Result()
        if query.startswith("UPDATE breaks SET form_requested_at"):
            return _Result((params[0],))
        if query.startswith("UPDATE group_members SET check_in_status"):
            return _Result((params[2],))
        if query.startswith("SELECT g.id, g.slot, g.table_id"):
            return _Result(self.group_row)
        if query.startswith("SELECT gm.attendee_id, gm.check_in_status"):
            return _Result(rows=self.members)
        raise AssertionError(f"Unexpected query: {query}")


class _Pool:
    def __init__(self, connection):
        self._connection = connection

    def connection(self):
        return self._connection


def _app():
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[current_attendee_id] = lambda: "viewer"
    return app


def test_form_now_requires_staff_token(monkeypatch):
    monkeypatch.setenv("STAFF_TOKEN", "s3cret")
    client = TestClient(_app())

    assert client.post("/api/staff/breaks/brk-tue-1530/form").status_code == 401
    response = client.post(
        "/api/staff/breaks/brk-tue-1530/form", headers={"x-staff-token": "wrong"}
    )
    assert response.status_code == 401


def test_form_now_marks_the_break_for_group_formation(monkeypatch):
    monkeypatch.setenv("STAFF_TOKEN", "s3cret")
    connection = _Connection()
    monkeypatch.setattr(routes, "pool", lambda: _Pool(connection))
    client = TestClient(_app())

    response = client.post(
        "/api/staff/breaks/brk-tue-1530/form", headers={"x-staff-token": "s3cret"}
    )

    assert response.status_code == 200
    assert response.json() == {"breakId": "brk-tue-1530", "status": "forming"}
    assert connection.calls[0][1] == ("brk-tue-1530",)


def test_rsvp_records_attendee_and_returns_going_status(monkeypatch):
    connection = _Connection()
    monkeypatch.setattr(routes, "pool", lambda: _Pool(connection))
    client = TestClient(_app())

    response = client.post("/api/breaks/brk-tue-1530/rsvp", json={"going": True})

    assert response.status_code == 200
    assert response.json() == {"breakId": "brk-tue-1530", "status": "going"}
    assert any(query.startswith("INSERT INTO break_rsvps") for query, _ in connection.calls)


@pytest.mark.parametrize("status", ["here", "on-the-way", "running-late"])
def test_check_in_persists_the_requested_status(monkeypatch, status):
    connection = _Connection()
    monkeypatch.setattr(routes, "pool", lambda: _Pool(connection))
    client = TestClient(_app())

    response = client.post("/api/groups/g-1/check-in", json={"status": status})

    assert response.status_code == 200
    assert response.json() == {"groupId": "g-1", "status": status}
    query, params = connection.calls[0]
    assert "check_in_status = %s" in query
    assert params[:2] == (status, status)


def test_current_group_shows_running_late_for_members_and_viewer(monkeypatch):
    connection = _Connection(
        group_row=(
            "g-1",
            "brk-tue-1530",
            "brk-tue-1530-tbl-quiet-window",
            datetime(2026, 11, 10, 22, 30, tzinfo=timezone.utc),
            "running-late",
        ),
        members=[("member", "running-late")],
    )
    monkeypatch.setattr(routes, "pool", lambda: _Pool(connection))
    app = _app()
    app.dependency_overrides[get_store] = lambda: type("Store", (), {"load": lambda self, _member: None})()

    response = TestClient(app).get("/api/groups/current")

    assert response.status_code == 200
    group = response.json()["group"]
    assert group["myStatus"] == "running-late"
    assert group["members"][0]["status"] == "running-late"
