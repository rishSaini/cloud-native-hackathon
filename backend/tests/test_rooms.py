"""R7: room state becomes Node taints and labels."""

from datetime import datetime, timezone

from app.controller.rooms import active_slots
from app.k8s.nodes import CLOSED_TAINT, FULL_TAINT, KWOK_TAINT, desired_taints, label_patch, venue_caps


def test_taints_follow_status_and_preserve_unowned_taints():
    other_taint = {"key": "example.com/custom", "value": "keep", "effect": "NoSchedule"}
    current = [KWOK_TAINT, other_taint, FULL_TAINT, CLOSED_TAINT]
    assert desired_taints("open", current) == [KWOK_TAINT, other_taint]
    assert desired_taints("full", current) == [KWOK_TAINT, other_taint, FULL_TAINT]
    assert desired_taints("closed", current) == [KWOK_TAINT, other_taint, CLOSED_TAINT]
    assert FULL_TAINT["effect"] == "NoSchedule" and CLOSED_TAINT["effect"] == "NoExecute"


def test_captions_down_removes_and_working_restores_the_label():
    caps = {"cap-c1", "cap-c2"}
    labels = {"affinity.dev/cap-c1": "true", "affinity.dev/cap-c2": "true"}
    assert label_patch(labels, caps, {"captions": "down"}) == {"affinity.dev/cap-c1": None}
    without = {"affinity.dev/cap-c2": "true"}
    assert label_patch(without, caps, {"captions": "working"}) == {"affinity.dev/cap-c1": "true"}
    assert label_patch(labels, caps, {}) == {}


def test_very_loud_removes_quiet_only_where_the_room_has_it():
    caps = venue_caps()
    assert "cap-c3" in caps["room-101"]
    assert label_patch({"affinity.dev/cap-c3": "true"}, caps["room-101"] & {"cap-c3"}, {"very_loud": True}) == {
        "affinity.dev/cap-c3": None}
    assert label_patch({}, caps["room-155"] & {"cap-c3"}, {"very_loud": True}) == {}


def test_active_slots_can_be_pinned(monkeypatch):
    monkeypatch.setenv("AFFINITY_CURRENT_SLOT", "tue-1430")
    assert active_slots(datetime(2026, 11, 9, 23, 0, tzinfo=timezone.utc)) == ["tue-1430", "tue-1600"]
    monkeypatch.delenv("AFFINITY_CURRENT_SLOT")
    assert active_slots(datetime(2026, 11, 10, 17, 0, tzinfo=timezone.utc)) == ["tue-0900", "tue-1030"]  # 10:00 MT: 9:00 is the latest started
