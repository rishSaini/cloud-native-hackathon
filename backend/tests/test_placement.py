"""R6: Pod specs stay opaque, seats never exceed allocatable, reasons are plain language."""

import json
from types import SimpleNamespace

import pytest

from app.cards.capabilities import MEANINGS
from app.controller.placement import FULL, NO_MATCH, WAITING, explain, room_of
from app.k8s.pods import HARD, STANDARD, build_pod
from app.k8s.seats import count_free
from app.search.ranking import RankedNode


def test_pod_spec_holds_only_random_ids_and_opaque_labels():
    pod = build_pod("7f3k", "tue-1430", ["cap-c3", "cap-c1"], [RankedNode("tue-1430-room-101", 100)], "team-x")
    text = json.dumps(pod).lower()
    for meaning in MEANINGS.values():
        assert meaning.lower() not in text
    assert pod["metadata"]["name"] == "attendee-7f3k-tue-1430"
    assert pod["metadata"]["labels"] == {"affinity.dev/attendee": "7f3k", "affinity.dev/slot": "tue-1430"}


def test_needs_become_required_affinity_and_hard_priority():
    pod = build_pod("7f3k", "tue-1430", ["cap-c3"], [], "team-x")
    terms = pod["spec"]["affinity"]["nodeAffinity"]["requiredDuringSchedulingIgnoredDuringExecution"]
    exprs = terms["nodeSelectorTerms"][0]["matchExpressions"]
    assert {"key": "affinity.dev/cap-c3", "operator": "Exists"} in exprs
    assert {"key": "affinity.dev/slot", "operator": "In", "values": ["tue-1430"]} in exprs
    assert pod["spec"]["priorityClassName"] == HARD
    assert "preferredDuringSchedulingIgnoredDuringExecution" not in pod["spec"]["affinity"]["nodeAffinity"]


def test_ranking_becomes_preferred_affinity_and_seat_limit_is_one():
    ranked = [RankedNode("tue-1430-room-101", 100), RankedNode("tue-1430-room-155", 1)]
    pod = build_pod("ab12", "tue-1430", [], ranked, "team-x")
    prefs = pod["spec"]["affinity"]["nodeAffinity"]["preferredDuringSchedulingIgnoredDuringExecution"]
    assert [p["weight"] for p in prefs] == [100, 1]
    assert pod["spec"]["priorityClassName"] == STANDARD
    assert pod["spec"]["containers"][0]["resources"]["limits"]["affinity.dev/seats"] == "1"


def test_unknown_capability_code_is_rejected():
    with pytest.raises(ValueError):
        build_pod("ab12", "tue-1430", ["cap-c99"], [], "team-x")


def node(name, seats):
    return SimpleNamespace(metadata=SimpleNamespace(name=name), status=SimpleNamespace(allocatable={"affinity.dev/seats": str(seats)}))


def pod(node_name, phase="Running", deleting=None):
    return SimpleNamespace(spec=SimpleNamespace(node_name=node_name), status=SimpleNamespace(phase=phase),
                           metadata=SimpleNamespace(deletion_timestamp=deleting))


def test_free_seats_subtract_bound_pods_and_never_go_negative():
    nodes = [node("tue-1430-room-101", 2), node("tue-1430-room-155", 5)]
    pods = [pod("tue-1430-room-101"), pod("tue-1430-room-101"), pod("tue-1430-room-101"),  # over-full on purpose
            pod("tue-1430-room-155"), pod(None), pod("tue-1430-room-155", phase="Succeeded"),
            pod("tue-1430-room-155", deleting="now")]
    assert count_free(nodes, pods) == {"tue-1430-room-101": 0, "tue-1430-room-155": 4}


def test_scheduler_text_becomes_plain_language():
    assert explain("0/4 nodes are available: 4 Insufficient affinity.dev/seats.") == FULL
    assert explain("0/4 nodes are available: 4 node(s) didn't match Pod's node affinity/selector.") == NO_MATCH
    assert explain("something else") == WAITING
    assert room_of("tue-1430-room-hall-b", "tue-1430") == "room-hall-b"
