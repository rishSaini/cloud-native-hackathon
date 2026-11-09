"""K12: the public board — words for status, one msearch, no identifiers."""

import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.board import routes
from app.es import get_es
from app.main import app

NOW = datetime(2026, 11, 10, 21, 40, tzinfo=UTC)  # 14:40 in Denver


def responses(states=(), incidents=(), latest=None, summary=None):
    return [
        {"hits": {"hits": [{"_source": s} for s in states]}},
        {"hits": {"hits": [{"_source": i} for i in incidents]}},
        {"aggregations": {"rooms": {"buckets": [
            {"key": room, "latest": {"value": ts}} for room, ts in (latest or {}).items()
        ]}}},
        {"hits": {"hits": [{"_source": summary}] if summary else []}},
    ]


def test_current_slot_uses_denver_time():
    assert routes.current_slot(NOW) == "tue-1430"
    assert routes.current_slot(datetime(2026, 11, 10, 14, 0, tzinfo=UTC)) == "tue-0900"  # 07:00 MT


def test_rooms_show_status_as_words_and_signals():
    board = routes.build_board(responses(
        states=[{"room": "room-251", "status": "full", "signals": {"captions": "down", "very_loud": True},
                 "seats_total": 120, "seats_free": 0}],
        incidents=[{"id": "inc-1", "room": "room-251", "kind": "captions", "state": "open"}],
        latest={"room-251": NOW.timestamp() * 1000 - 3 * 60000},
    ), "tue-1430", NOW)
    rooms = {r["id"]: r for r in board["rooms"]}
    assert list(rooms) == routes.ROOMS
    r251 = rooms["room-251"]
    assert r251["status"] == "FULL" and r251["taken"] == 120 and r251["seatsFree"] == 0
    assert r251["openIncident"] and r251["incident"]["type"] == "captions"
    assert r251["reportedMinutesAgo"] == 3 and r251["climate"]["noise"] == "loud"
    assert rooms["room-101"]["status"] == "OPEN" and rooms["room-101"]["captions"] == "unknown"
    assert rooms["room-101"]["reportedMinutesAgo"] is None


def test_board_holds_no_identifiers():
    board = routes.build_board(responses(
        states=[{"room": "room-101", "status": "open", "signals": {}, "changed_at": "x",
                 "traceparent": "00-abc-def-01"}],
    ), "tue-1430", NOW)
    text = json.dumps(board)
    assert board["attendees"] == [] and "traceparent" not in text and "reporter_hash" not in text


def test_nobody_alone_rate_comes_from_the_summary():
    board = routes.build_board(responses(summary={"break": "brk-tue-1530", "opted_in": 40, "alone": 1}), "tue-1430", NOW)
    assert board["nobodyAloneRate"] == 0.975 and board["alone"] == 1
    assert "nobodyAloneRate" not in routes.build_board(responses(), "tue-1430", NOW)


def test_route_makes_one_msearch(monkeypatch):
    calls = []

    class FakeES:
        def msearch(self, searches):
            calls.append(searches)
            return {"responses": responses()}

    app.dependency_overrides[get_es] = FakeES
    try:
        body = TestClient(app).get("/api/board", params={"slot": "tue-1600"}).json()
    finally:
        app.dependency_overrides.clear()
    assert len(calls) == 1 and len(calls[0]) == 8  # 4 searches, each a header and a body
    assert body["board"]["slot"] == "tue-1600"
