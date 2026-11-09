"""R2: venue Nodes match the contract and Karthik's talk nodes, and stay opaque."""

import importlib.util
import json
from pathlib import Path

from app.cards import capabilities

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("gen_nodes", ROOT / "scripts" / "gen_nodes.py")
gen_nodes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen_nodes)

VENUE = json.loads((ROOT / "data" / "venue.json").read_text())
NODES = gen_nodes.build(VENUE)


def test_34_nodes_20_talk_14_table():
    kinds = [n["metadata"]["labels"]["affinity.dev/kind"] for n in NODES]
    assert len(NODES) == 34 and kinds.count("talk") == 20 and kinds.count("table") == 14


def test_talk_node_names_follow_the_contract():
    talk_nodes = {n["metadata"]["name"] for n in NODES if n["metadata"]["labels"]["affinity.dev/kind"] == "talk"}
    slots = ["tue-0900", "tue-1030", "tue-1330", "tue-1430", "tue-1600"]
    rooms = ["room-101", "room-155", "room-251", "room-hall-b"]
    assert talk_nodes == {f"{s}-{r}" for s in slots for r in rooms}
    assert "brk-tue-1530-tbl-quiet-window" in {n["metadata"]["name"] for n in NODES}


def test_every_node_has_seats_and_the_kwok_taint():
    for n in NODES:
        assert int(n["status"]["allocatable"]["affinity.dev/seats"]) > 0
        assert n["status"]["capacity"] == n["status"]["allocatable"]
        assert n["metadata"]["labels"]["kubernetes.io/hostname"] == n["metadata"]["name"]
        assert n["spec"]["taints"][0]["key"] == "kwok.x-k8s.io/node"


def test_nodes_hold_only_opaque_capability_codes():
    text = (ROOT / "deploy" / "kwok" / "nodes.yaml").read_text().lower()
    for meaning in capabilities.MEANINGS.values():
        assert meaning.lower() not in text
    used = {c for group in VENUE["rooms"] + VENUE["tables"] for c in group["caps"]}
    assert used <= set(capabilities.MEANINGS)


def test_committed_nodes_yaml_is_up_to_date():
    assert (ROOT / "deploy" / "kwok" / "nodes.yaml").read_text() == gen_nodes.to_yaml(NODES)


def test_signal_map_points_at_known_codes():
    assert set(capabilities.SIGNAL_REMOVES) == {"captions_down", "access_blocked", "very_loud"}
    assert capabilities.label("cap-c3") == "affinity.dev/cap-c3"
