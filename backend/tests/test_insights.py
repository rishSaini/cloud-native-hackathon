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
