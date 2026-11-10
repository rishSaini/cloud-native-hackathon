"""K17: anonymous room and equity insights."""

from datetime import UTC, datetime
from types import SimpleNamespace as NS

from app.controller.insights import occupancy, room_of
from app.insights.routes import MIN_GROUP, room_series, wait_stats


def node(name, slot, seats):
    return NS(metadata=NS(name=name, labels={"affinity.dev/slot": slot}),
              status=NS(allocatable={"affinity.dev/seats": str(seats)}))


def pod(node_name, phase="Running"):
    return NS(spec=NS(node_name=node_name), status=NS(phase=phase), metadata=NS(deletion_timestamp=None))


def test_occupancy_counts_bound_pods_only():
    nodes = [node("tue-0900-room-101", "tue-0900", 10), node("tue-0900-room-155", "tue-0900", 4)]
    pods = [pod("tue-0900-room-101"), pod("tue-0900-room-101"), pod(None), pod("tue-0900-room-155", "Succeeded")]
    rows = {r["room"]: r for r in occupancy(nodes, pods)}
    assert rows["room-101"]["taken"] == 2 and rows["room-101"]["seats"] == 10
    assert rows["room-155"]["taken"] == 0
    assert room_of("tue-0900-room-101", "tue-0900") == "room-101"


def test_small_groups_are_hidden_and_gap_needs_both():
    stats = wait_stats([(True, MIN_GROUP - 1, 9.0, 20.0), (False, 50, 3.0, 6.0)])
    assert stats["withNeeds"] == {"count": MIN_GROUP - 1, "hidden": True}
    assert stats["withoutNeeds"]["p95Seconds"] == 6.0
    assert stats["p95GapSeconds"] is None


def test_gap_is_needs_minus_no_needs():
    stats = wait_stats([(True, 12, 4.0, 11.5), (False, 40, 3.0, 6.0)])
    assert stats["p95GapSeconds"] == 5.5


def test_room_series_sorts_fullest_first():
    at = datetime(2026, 11, 10, 16, 0, tzinfo=UTC)
    rooms = room_series(
        [("room-101", "n1", 10, 2), ("room-155", "n2", 4, 4)],
        [("room-155", at, 3), ("room-155", at, 4)],
    )
    assert [r["room"] for r in rooms] == ["room-155", "room-101"]
    assert rooms[0]["occupancy"] == 1.0 and len(rooms[0]["history"]) == 2
    assert "attendee" not in str(rooms)


def _hist(start, pairs):
    from datetime import timedelta
    return [{"at": (start + timedelta(seconds=s)).isoformat(), "taken": v} for s, v in pairs]


def test_engagement_held_room_has_no_drop():
    from app.insights.routes import engagement
    start = datetime(2026, 11, 10, 16, 0, tzinfo=UTC)
    e = engagement(_hist(start, [(0, 5), (20, 30), (60, 40), (120, 38)]), start)
    assert e["peak"] == 40 and e["peakAtSeconds"] == 60 and e["now"] == 38
    assert e["word"] == "HELD" and e["drop"] is None


def test_engagement_finds_the_sharpest_drop():
    from app.insights.routes import engagement
    start = datetime(2026, 11, 10, 16, 0, tzinfo=UTC)
    e = engagement(_hist(start, [(0, 100), (90, 98), (100, 80), (110, 60), (200, 58)]), start)
    assert e["word"] == "DROPPED" and e["kept"] == 0.58
    assert e["drop"] == {"people": 38, "fromSeconds": 90, "toSeconds": 110}


def test_engagement_empty_history():
    from app.insights.routes import engagement
    assert engagement([], datetime(2026, 11, 10, tzinfo=UTC)) is None


def test_insights_defaults_to_the_slot_with_the_newest_numbers(monkeypatch):
    """No ?slot= -> the slot of the newest occupancy sample, not the clock's slot."""
    import app.insights.routes as routes

    seen = []

    class Conn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, params=()):
            seen.append(params)
            rows = [("tue-1330",)] if "ORDER BY at DESC LIMIT 1" in sql else []
            return type("R", (), {"fetchone": lambda s: rows[0] if rows else None, "fetchall": lambda s: rows})()

    monkeypatch.setattr(routes, "pool", lambda: type("P", (), {"connection": lambda s: Conn()})())
    monkeypatch.setattr(routes, "talk_titles", lambda nodes: {})
    body = routes.insights(slot=None)
    assert body["slot"] == "tue-1330"
    assert body["totals"] == {"seats": 0, "taken": 0, "occupancy": None}
